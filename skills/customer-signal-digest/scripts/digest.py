#!/usr/bin/env python3
"""Build the customer signal digest: read, redact, dedupe, cluster, rank, quote, then render.

Usage:
  python3 scripts/digest.py build --run run --as-of 2026-11-26 \\
      --zendesk tickets-*.json --intercom conversations-*.json \\
      --csv "source=calls,kind=call,file=call-notes.csv,text=notes,person=contact" \\
      --csv "source=nps,kind=nps,file=nps.csv,text=comment,score=score" \\
      --accounts accounts.csv --themes themes.json
  python3 scripts/digest.py render --run run [--notes run/notes.json]
  python3 scripts/digest.py inspect --zendesk tickets-*.json --csv-file call-notes.csv nps.csv

build writes run/digest.json. Only redacted text is written: raw text and known names stay in memory, and
names are kept only as salted hashes (run/fingerprints.json) so later notes can be checked against them.
build also writes run/opportunities.csv, one row per opportunity, for a tracker import.
render checks notes.json with validate.py and writes run/digest.md. Any error stops the render.
inspect describes each input (counts, dates, accounts, CSV columns, and which columns look personal) without showing text.

--redact-terms names a text file of extra terms to redact, one per line: staff names, customer company names, codes.

--csv takes comma-separated key=value pairs: source, kind (call, nps, survey, ticket, conversation) and file
are required; id, text, date, account, theme, score and person (repeatable with +, for example
person=contact+email) name the columns and default to id, text, created_at, account, none, none, none.

These scripts read files and write files. They make no network calls.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import re
import secrets
import sys
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036  (the guard exists for older interpreters)
    sys.exit(f"customer-signal-digest needs Python 3.11 or later (this is {sys.version.split()[0]}); try python3.12")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))

import cluster  # noqa: E402  (sibling scripts, found through the path above)
import dedupe  # noqa: E402
import landing_brief  # noqa: E402  (vendored unchanged from the Leader Report)
import loop  # noqa: E402
import rank  # noqa: E402
import redact  # noqa: E402
import render_html  # noqa: E402
import signals  # noqa: E402
import validate  # noqa: E402

VERSION = "0.3.4"
MAX_QUOTE = 240


def parse_csv_spec(spec: str) -> dict:
    out: dict = {}
    for part in spec.split(","):
        key, sep, value = part.partition("=")
        if not sep:
            raise signals.Refused(f"--csv takes key=value pairs separated by commas. Got {part!r} in {spec!r}.")
        out[key.strip()] = value.strip()
    missing = [k for k in ("source", "kind", "file") if not out.get(k)]
    if missing:
        raise signals.Refused(f"--csv needs {', '.join(missing)}. Got {spec!r}.")
    unknown = set(out) - {"source", "kind", "file", "id", "text", "date", "account", "theme", "score", "person"}
    if unknown:
        raise signals.Refused(f"--csv does not know {', '.join(sorted(unknown))}.")
    return out


def quote_of(text: str) -> str:
    """The opening of a signal, cut at a sentence or word boundary, never mid-word."""
    flat = " ".join(text.split())
    if len(flat) <= MAX_QUOTE:
        return flat
    cut = flat[:MAX_QUOTE]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[: end + 1] if end > MAX_QUOTE // 2 else cut[: cut.rfind(" ")] + " ..."


def pick_quotes(opp: dict, known: list[str], limit: int) -> tuple[list[dict], int]:
    """Up to `limit` quotes, newest first, one per account before any account repeats. A quote that still looks personal is withheld."""
    order = sorted(opp["signals"], key=lambda s: (s["created"] or "", s["id"]), reverse=True)
    first, repeat, seen = [], [], set()
    for s in order:
        key = s["account"] or s["id"]
        (repeat if key in seen else first).append(s)
        seen.add(key)
    quotes, withheld = [], 0
    for s in first + repeat:
        if len(quotes) == limit:
            break
        q = quote_of(s["text"])
        if redact.leaks(q, known):
            withheld += 1
            continue
        quotes.append({"text": q, "ids": [s["id"], *s["duplicates"]], "account": s["account"], "created": s["created"], "kind": s["kind"]})
    return quotes, withheld


def build(args: argparse.Namespace) -> int:
    try:
        as_of = datetime.date.fromisoformat(args.as_of)
    except ValueError:
        raise signals.Refused(f"--as-of takes YYYY-MM-DD. Got {args.as_of!r}.") from None
    run = Path(args.run)
    run.mkdir(parents=True, exist_ok=True)
    allsig: list[dict] = []
    known: set[str] = set()
    inputs: list[dict] = []
    left_out: dict[str, int] = {}
    if args.zendesk:
        got, k = signals.from_zendesk(args.zendesk, args.theme_prefix)
        allsig += got
        known |= k
        inputs.append({"system": "Zendesk", "files": [Path(p).name for p in args.zendesk], "signals": len(got)})
    if args.intercom:
        got, k = signals.from_intercom(args.intercom, args.theme_prefix, args.intercom_account_attribute)
        allsig += got
        known |= k
        inputs.append({"system": "Intercom", "files": [Path(p).name for p in args.intercom], "signals": len(got)})
    for spec in args.csv:
        c = parse_csv_spec(spec)
        got, k, no_text = signals.from_csv(
            c["file"],
            c["source"],
            c["kind"],
            id_col=c.get("id", "id"),
            text_col=c.get("text", "text"),
            date_col=c.get("date", "created_at"),
            account_col=c.get("account", "account") or None,
            theme_col=c.get("theme") or None,
            score_col=c.get("score") or None,
            person_cols=tuple(p for p in c.get("person", "").split("+") if p),
        )
        allsig += got
        known |= k
        inputs.append({"system": f"CSV ({c['source']})", "files": [Path(c["file"]).name], "signals": len(got)})
        if no_text:
            left_out[f"{c['source']} rows with no text"] = no_text
    if not allsig:
        raise signals.Refused("no signals were read. Pass --zendesk, --intercom or --csv.")
    for flag, value in (("--since", args.since), ("--until", args.until)):
        if value:
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                raise signals.Refused(f"{flag} takes YYYY-MM-DD. Got {value!r}.") from None
    if args.since:
        before = len(allsig)
        allsig = [s for s in allsig if s["created"] and s["created"] >= args.since]
        left_out[f"signals before {args.since} or undated"] = before - len(allsig)
    until = min(args.until or as_of.isoformat(), as_of.isoformat())
    before = len(allsig)
    allsig = [s for s in allsig if s["created"] <= until or not s["created"]]
    if before - len(allsig):
        left_out[f"signals after {until}"] = before - len(allsig)
    if args.redact_terms:
        try:
            extra = [line.strip() for line in Path(args.redact_terms).read_text(encoding="utf-8").splitlines()]
        except (OSError, UnicodeDecodeError) as e:
            raise signals.Refused(f"cannot read {args.redact_terms} ({e}).") from None
        known |= {t for t in extra if t and not t.startswith("#")}
    known_list = sorted(known)
    redacted = redact.redact_signals(allsig, known_list)
    kept, merged = dedupe.dedupe(allsig)
    themes = cluster.load_themes(args.themes)
    opps = cluster.cluster(kept, themes)
    arr = signals.read_accounts(args.accounts) if args.accounts else {}
    base = args.customer_base or (signals.count_accounts(args.accounts) if args.accounts else None)
    result = rank.rank(opps, as_of, arr, rank.parse_weights(args.weights), customer_base=base)
    named = sorted({a for o in result["opportunities"] for a in o["figures"]["account_ids"]})
    dated = sorted(s["created"] for s in allsig if s["created"])
    withheld = 0
    for o in result["opportunities"]:
        o["quotes"], w = pick_quotes(o, known_list, args.max_quotes)
        withheld += w
        for s in o["signals"]:
            s.pop("theme", None)
    salt = secrets.token_hex(16)
    (run / "fingerprints.json").write_text(json.dumps({"salt": salt, "fingerprints": redact.fingerprints(known_list, salt)}, indent=2) + "\n")
    digest = {
        "tool": "customer-signal-digest",
        "version": VERSION,
        "as_of": as_of.isoformat(),
        "window": {"from": args.since or (dated[0] if dated else None), "to": until},
        "illustrative": bool(args.illustrative),
        "inputs": inputs,
        "counts": {
            "read": sum(i["signals"] for i in inputs),
            "in_window": len(allsig),
            "duplicates_merged": merged,
            "kept": len(kept),
            "opportunities": len(result["opportunities"]),
            "redacted_spans": dict(sorted(redacted.items())),
            "quotes_withheld": withheld,
            "left_out": left_out,
        },
        **result,
        "arr_by_account": {a: arr[a] for a in named if a in arr},
    }
    (run / "digest.json").write_text(json.dumps(digest, indent=2) + "\n")
    write_csv(run / "opportunities.csv", digest)
    print(f"digest: {digest['counts']['kept']} signals ({merged} duplicates merged) in {len(result['opportunities'])} opportunities.")
    print(f"digest: {sum(redacted.values())} personal-data spans redacted; {withheld} quotes withheld. Written to {run / 'digest.json'}.")
    if not result["arr_used"] and arr:
        cov = result["arr_coverage"]
        print(f"digest: ARR is known for {cov['accounts_with_arr']} of {cov['accounts_named']} accounts, so it is shown but left out of the score.")
    if args.loop:
        learn(args, digest)
    return 0


def learn(args: argparse.Namespace, digest: dict) -> None:
    """Step 04 Learn: write the `signals` key of landing/<bet>.json and, with --html, the page for leaders and its Markdown twin."""
    if not args.bet:
        raise signals.Refused("--loop needs --bet, the bet's slug (its record is landing/<bet>.json).")
    folder = Path(args.loop)
    try:
        record = loop.load(folder, args.bet)
        brief_file = loop.brief_path(folder, record, args.brief)
    except loop.RecordError as e:
        raise signals.Refused(str(e)) from None
    try:
        brief = landing_brief.parse(brief_file.read_text(encoding="utf-8"))
    except landing_brief.BriefError as e:
        raise signals.Refused(f"the brief {brief_file} is not complete, so nothing was written. The parser says: {e}") from None
    except OSError as e:
        raise signals.Refused(f"cannot read the brief {brief_file} ({e}).") from None
    key = loop.signals_key(digest, record, brief, brief_file, args.bet)
    # The page and its twin are rendered before the record is written, so a render failure leaves the record as it was.
    pages = []
    if args.html:
        html_path = Path(args.html)
        pages = [(html_path, render_html.page(key, args.bet)), (html_path.with_suffix(".md"), render_html.markdown(key, args.bet))]
    out = loop.write(folder, args.bet, brief_file, record, key)
    print(f"digest: wrote the signals key of {out} ({key['check'] or 'not checked'}).")
    for path, text in pages:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if pages:
        print(f"digest: wrote {pages[0][0]} and {pages[1][0]}.")


CSV_COLUMNS = (
    "rank",
    "rank_range",
    "id",
    "name",
    "score",
    "accounts",
    "arr",
    "signals",
    "mentions",
    "last_30_days",
    "prior_30_days",
    "account_share",
    "last_seen",
    "detractors",
    "promoters",
    "accounts_by_arr",
    "source_ids",
    "illustrative",
)


def write_csv(path: Path, digest: dict) -> None:
    """One row per opportunity, for a tracker import. Redacted names only; no quotes."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for o in digest["opportunities"]:
        f = o["figures"]
        ids = " ".join(sorted(i for s in o["signals"] for i in [s["id"], *s["duplicates"]]))
        w.writerow(
            [
                o["rank"],
                _range(o["rank_range"]),
                o["id"],
                o["name"],
                f"{o['score']:.4f}",
                f["accounts"],
                "" if f["arr"] is None else f["arr"],
                f["signals"],
                f["mentions"],
                f["last_30_days"],
                f["prior_30_days"],
                "" if f["account_share"] is None else f["account_share"],
                f["last_seen"] or "",
                f["detractors"],
                f["promoters"],
                " ".join(f["accounts_by_arr"]),
                ids,
                "yes" if digest["illustrative"] else "no",
            ]
        )
    path.write_text(buf.getvalue())


PERSONAL_HEADER = re.compile(r"name|email|e-mail|contact|phone|mobile|person|requester|author|customer_?name|address", re.I)


def inspect(args: argparse.Namespace) -> int:
    """What each input holds, without showing any text: counts, date range, and for a CSV its columns and which look personal."""
    for p in args.zendesk:
        got, known = signals.from_zendesk([p], args.theme_prefix)
        _describe(f"Zendesk {Path(p).name}", got, f"{len(known)} requester names and emails will be redacted")
    for p in args.intercom:
        got, known = signals.from_intercom([p], args.theme_prefix, args.intercom_account_attribute)
        _describe(f"Intercom {Path(p).name}", got, f"{len(known)} author names and emails will be redacted")
        attrs = sorted({k for c in signals.load_json(Path(p)).get("conversations", []) for k in (c.get("custom_attributes") or {})})
        if attrs and not args.intercom_account_attribute:
            print(f"  Custom attributes, one may name the account (--intercom-account-attribute): {', '.join(attrs)}.")
    for p in args.csv_file:
        rows = signals.read_csv(Path(p))
        cols = list(rows[0]) if rows else []
        personal = [c for c in cols if PERSONAL_HEADER.search(c)]
        print(f"CSV {Path(p).name}: {len(rows)} rows. Columns: {', '.join(cols) or 'none'}.")
        if personal:
            print(f"  May hold personal data, pass as person=: {'+'.join(personal)}.")
    return 0


def _describe(label: str, got: list[dict], note: str) -> None:
    dates = sorted(s["created"] for s in got if s["created"])
    span = f"{dates[0]} to {dates[-1]}" if dates else "no dates"
    accounts = len({s["account"] for s in got if s["account"]})
    tagged = sum(1 for s in got if s["theme"])
    print(f"{label}: {len(got)} records, {span}, {accounts} accounts, {tagged} with a theme tag; {note}.")


def _md(text: str) -> str:
    """Source text shown as data: no markup, links, HTML or headings from a ticket survive."""
    return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", text)


def _share(f: dict) -> str:
    return "" if f["account_share"] is None else f" ({f['account_share']}% of the customer base)"


def _range(r: list[int]) -> str:
    return str(r[0]) if r[0] == r[1] else f"{r[0]} to {r[1]}"


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def _money(v: float | None) -> str:
    return "n/a" if v is None else f"{v:,.0f}"


def render_md(digest: dict, notes: dict) -> str:
    tag = " (Illustrative)" if digest["illustrative"] else ""
    c = digest["counts"]
    lines = [f"# Customer signal digest{tag}", ""]
    if digest["illustrative"]:
        lines += ["> **Illustrative.** Every figure below is sample data from an invented company.", ""]
    srcs = "; ".join(f"{i['system']}: {i['signals']}" for i in digest["inputs"])
    lines += [
        f"As of {digest['as_of']}. Read {c['read']} signals ({srcs}). {c['duplicates_merged']} duplicates merged, "
        f"{c['kept']} signals kept, {c['opportunities']} opportunities. {sum(c['redacted_spans'].values())} personal-data spans redacted "
        f"before anything was clustered or quoted.",
        "",
    ]
    w = digest["weights"]
    arr_note = "ARR averaged into reach" if digest["arr_used"] else "ARR not in the score"
    cov = digest["arr_coverage"]
    lines += [
        f"Ranked in code: score = {w['reach']} reach + {w['frequency']} frequency + {w['recency']} recency "
        f"(half-life {digest['half_life_days']} days; {arr_note}, known for {cov['accounts_with_arr']} of {cov['accounts_named']} accounts). "
        "Scores are relative to this run: compare ranks across digests, not scores.",
        "Rank range is the best and worst rank under the chosen weights and three alternatives (reach-, frequency- and "
        "recency-heavy). A wide range means the order rests on the weights. Last 30 days and prior 30 days are signal counts, not a forecast.",
        "",
        f"| Rank | Rank range | Opportunity | Score | Accounts | ARR | Signals | Last 30 days | Prior 30 days | Last seen |{' Data |' if tag else ''}",
        f"|---|---|---|---|---|---|---|---|---|---|{'---|' if tag else ''}",
    ]
    for o in digest["opportunities"]:
        f = o["figures"]
        title = (notes.get(o["id"]) or {}).get("title") or o["name"]
        lines.append(
            f"| {o['rank']} | {_range(o['rank_range'])} | {_md(title)}{' (praise only)' if f['praise_only'] else ''} | {o['score']:.2f} | "
            f"{f['accounts']} | {_money(f['arr'])} | {f['signals']} | {f['last_30_days']} | {f['prior_30_days']} | "
            f"{f['last_seen'] or 'n/a'} |{' Illustrative |' if tag else ''}"
        )
    for o in digest["opportunities"]:
        f, note = o["figures"], notes.get(o["id"]) or {}
        lines += ["", f"## {o['rank']}. {_md(note.get('title') or o['name'])}{tag}", ""]
        if note.get("summary"):
            lines += [_md(note["summary"]), ""]
        lines += [
            f"{plural(f['accounts'], 'account')}{_share(f)}, {plural(f['signals'], 'signal')} ({plural(f['mentions'], 'mention')}), "
            f"last seen {f['last_seen'] or 'n/a'} "
            f"({plural(f['days_since_last'], 'day') if f['days_since_last'] is not None else 'n/a'} before {digest['as_of']}). "
            f"Grouped by {o['how']}. Components: reach {o['components']['reach']:.2f}, frequency {o['components']['frequency']:.2f}, "
            f"recency {o['components']['recency']:.2f}. "
            f"NPS: {plural(f['detractors'], 'detractor')}, {plural(f['passives'], 'passive')}, {plural(f['promoters'], 'promoter')}.",
            "",
        ]
        if f["praise_only"]:
            lines += ["Every signal here is an NPS promoter: this is praise, not a problem to solve.", ""]
        if f["accounts_by_arr"]:
            lines += [f"Accounts to talk to next, highest ARR first: {', '.join(f['accounts_by_arr'][:5])}.", ""]
        for q in o["quotes"]:
            lines += [f"> {_md(q['text'])}", f"> ({', '.join(q['ids'])}; {q['kind']}, {q['created'] or 'undated'})", ""]
        if not o["quotes"]:
            lines += ["No quote passed the personal-data check. The signal IDs are in the ledger.", ""]
    lines += ["## Evidence ledger", "", "| Opportunity | Figure | Value | How it was computed |", "|---|---|---|---|"]
    for o in digest["opportunities"]:
        f = o["figures"]
        ids = ", ".join(sorted(i for s in o["signals"] for i in [s["id"], *s["duplicates"]]))
        rows = [
            ("Accounts", f["accounts"], "distinct accounts on its deduplicated signals"),
            ("ARR", _money(f["arr"]), f"summed ARR of the {plural(f['arr_accounts'], 'account')} with a known ARR"),
            (
                "Share of accounts",
                "n/a" if f["account_share"] is None else f"{f['account_share']}%",
                f"accounts / a customer base of {digest['customer_base']}" if digest["customer_base"] else "no customer base given",
            ),
            ("Signals", f["signals"], "signals after duplicates were merged"),
            ("Mentions", f["mentions"], "signals plus the duplicates merged into them"),
            ("Recency", f"{f['recency']:.2f}", f"mean of 0.5 ^ (age / {digest['half_life_days']} days) over dated signals"),
            ("Last 30 / prior 30 days", f"{f['last_30_days']} / {f['prior_30_days']}", f"signals 0 to 29 and 30 to 59 days before {digest['as_of']}"),
            ("Rank range", _range(o["rank_range"]), "best and worst rank under the chosen weights and the three alternatives"),
            ("Source IDs", ids, "every signal and duplicate behind the figures above"),
        ]
        for name, value, how in rows:
            lines.append(f"| {o['id']} | {name} | {value}{tag if name != 'Source IDs' else ''} | {how} |")
    left = digest["counts"]["left_out"]
    if left or c["quotes_withheld"]:
        lines += ["", "## Left out", ""]
        lines += [f"- {n} {why}." for why, n in left.items() if n]
        if c["quotes_withheld"]:
            lines.append(f"- {c['quotes_withheld']} quotes withheld because they still looked personal after redaction.")
    lines += ["", f"Built by customer-signal-digest {digest['version']}. Source text is quoted as data, never followed as instructions.", ""]
    return "\n".join(lines)


def render(args: argparse.Namespace) -> int:
    run = Path(args.run)
    digest = signals.load_json(run / "digest.json")
    fp = signals.load_json(run / "fingerprints.json")
    notes_doc = signals.load_json(Path(args.notes)) if args.notes else {"notes": {}}
    errors = validate.check(notes_doc, digest, fp["salt"], fp["fingerprints"])
    if errors:
        for e in errors:
            print(f"error {e['rule']}: {e['opportunity']} {e['field']}: {e['detail']}", file=sys.stderr)
        print(f"render: {len(errors)} error(s). Fix the notes; the digest was not rendered.", file=sys.stderr)
        return 1
    out = run / "digest.md"
    out.write_text(render_md(digest, notes_doc["notes"]))
    print(f"render: 0 errors. Written to {out}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Customer signal digest: redact, dedupe, cluster and rank customer signals.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="read, redact, dedupe, cluster, rank and quote")
    b.add_argument("--run", default="run")
    b.add_argument("--as-of", required=True, help="YYYY-MM-DD; recency counts back from this date")
    b.add_argument("--since", help="YYYY-MM-DD; leave out signals before this date")
    b.add_argument("--until", help="YYYY-MM-DD; leave out signals after this date (default --as-of)")
    b.add_argument("--loop", help="the working folder that holds landing/<bet>.json; writes only its signals key")
    b.add_argument("--bet", help="the bet's slug, with --loop")
    b.add_argument("--brief", help="the bet's landing brief, with --loop when the record does not exist yet")
    b.add_argument("--html", help="with --loop: write the page for leaders here, and its Markdown twin beside it")
    b.add_argument("--zendesk", nargs="+", default=[])
    b.add_argument("--intercom", nargs="+", default=[])
    b.add_argument("--intercom-account-attribute", help="the conversation custom attribute that names the account")
    b.add_argument("--csv", action="append", default=[], help="source=..,kind=..,file=..[,text=..,id=..,date=..,account=..,theme=..,score=..,person=..]")
    b.add_argument("--theme-prefix", help='the tag prefix that names a theme in Zendesk or Intercom, for example "theme:"')
    b.add_argument("--themes", help="themes.json: opportunities with keywords")
    b.add_argument("--accounts", help="a CSV of account,arr")
    b.add_argument("--weights", help="reach=0.5,frequency=0.3,recency=0.2")
    b.add_argument("--max-quotes", type=int, default=3)
    b.add_argument("--illustrative", action="store_true", help="mark every figure as illustrative (sample data)")
    b.add_argument("--customer-base", type=int, help="the number of customer accounts; defaults to the rows in --accounts")
    b.add_argument("--redact-terms", help="a text file, one term per line: extra names, company names or codes to redact")
    i = sub.add_parser("inspect", help="describe each input without showing its text, before a build")
    i.add_argument("--zendesk", nargs="+", default=[])
    i.add_argument("--intercom", nargs="+", default=[])
    i.add_argument("--csv-file", nargs="+", default=[], help="CSV files to list columns for")
    i.add_argument("--theme-prefix")
    i.add_argument("--intercom-account-attribute")
    r = sub.add_parser("render", help="validate notes and write digest.md")
    r.add_argument("--run", default="run")
    r.add_argument("--notes", help='notes.json: {"notes": {"<id>": {"title", "summary"}}}')
    args = ap.parse_args(argv)
    try:
        return {"build": build, "render": render, "inspect": inspect}[args.cmd](args)
    except signals.Refused as e:
        print(f"digest: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
