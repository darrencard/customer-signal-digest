#!/usr/bin/env python3
"""Build the customer signal digest: read, redact, dedupe, cluster, rank, quote, then render.

Usage:
  python3 scripts/digest.py build --run run --as-of 2026-11-26 \\
      --zendesk tickets-*.json --intercom conversations-*.json \\
      --csv "source=calls,kind=call,file=call-notes.csv,text=notes,person=contact" \\
      --csv "source=nps,kind=nps,file=nps.csv,text=comment,score=score" \\
      --accounts accounts.csv --themes themes.json
  python3 scripts/digest.py render --run run [--notes run/notes.json]

build writes run/digest.json. Only redacted text is written: raw text and known names stay in memory, and
names are kept only as salted hashes (run/fingerprints.json) so later notes can be checked against them.
render checks notes.json with validate.py and writes run/digest.md. Any error stops the render.

--csv takes comma-separated key=value pairs: source, kind (call, nps, survey, ticket, conversation) and file
are required; id, text, date, account, theme, score and person (repeatable with +, for example
person=contact+email) name the columns and default to id, text, created_at, account, none, none, none.

These scripts read files and write files. They make no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cluster  # noqa: E402  (sibling scripts, found through the path above)
import dedupe  # noqa: E402
import rank  # noqa: E402
import redact  # noqa: E402
import signals  # noqa: E402
import validate  # noqa: E402

VERSION = "0.1.0"
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
    if args.since:
        before = len(allsig)
        allsig = [s for s in allsig if s["created"] and s["created"] >= args.since]
        left_out[f"signals before {args.since} or undated"] = before - len(allsig)
    allsig = [s for s in allsig if s["created"] <= as_of.isoformat() or not s["created"]]
    known_list = sorted(known)
    redacted = redact.redact_signals(allsig, known_list)
    kept, merged = dedupe.dedupe(allsig)
    themes = cluster.load_themes(args.themes)
    opps = cluster.cluster(kept, themes)
    arr = signals.read_accounts(args.accounts) if args.accounts else {}
    result = rank.rank(opps, as_of, arr, rank.parse_weights(args.weights))
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
    }
    (run / "digest.json").write_text(json.dumps(digest, indent=2) + "\n")
    print(f"digest: {digest['counts']['kept']} signals ({merged} duplicates merged) in {len(result['opportunities'])} opportunities.")
    print(f"digest: {sum(redacted.values())} personal-data spans redacted; {withheld} quotes withheld. Written to {run / 'digest.json'}.")
    if not result["arr_used"] and arr:
        cov = result["arr_coverage"]
        print(f"digest: ARR is known for {cov['accounts_with_arr']} of {cov['accounts_named']} accounts, so it is shown but left out of the score.")
    return 0


def _md(text: str) -> str:
    """Source text shown as data: no markup, links, HTML or headings from a ticket survive."""
    return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", text)


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
        f"(half-life {digest['half_life_days']} days; {arr_note}, known for {cov['accounts_with_arr']} of {cov['accounts_named']} accounts).",
        "",
        f"| Rank | Opportunity | Score | Accounts | ARR | Signals | Mentions | Last seen | Detractors |{' Data |' if tag else ''}",
        f"|---|---|---|---|---|---|---|---|---|{'---|' if tag else ''}",
    ]
    for o in digest["opportunities"]:
        f = o["figures"]
        title = (notes.get(o["id"]) or {}).get("title") or o["name"]
        lines.append(
            f"| {o['rank']} | {_md(title)} | {o['score']:.2f} | {f['accounts']} | {_money(f['arr'])} | {f['signals']} | {f['mentions']} | "
            f"{f['last_seen'] or 'n/a'} | {f['detractors']} |{' Illustrative |' if tag else ''}"
        )
    for o in digest["opportunities"]:
        f, note = o["figures"], notes.get(o["id"]) or {}
        lines += ["", f"## {o['rank']}. {_md(note.get('title') or o['name'])}{tag}", ""]
        if note.get("summary"):
            lines += [_md(note["summary"]), ""]
        lines += [
            f"{plural(f['accounts'], 'account')}, {plural(f['signals'], 'signal')} ({plural(f['mentions'], 'mention')}), last seen {f['last_seen'] or 'n/a'} "
            f"({plural(f['days_since_last'], 'day') if f['days_since_last'] is not None else 'n/a'} before {digest['as_of']}). "
            f"Grouped by {o['how']}. Components: reach {o['components']['reach']:.2f}, frequency {o['components']['frequency']:.2f}, "
            f"recency {o['components']['recency']:.2f}.",
            "",
        ]
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
            ("Signals", f["signals"], "signals after duplicates were merged"),
            ("Mentions", f["mentions"], "signals plus the duplicates merged into them"),
            ("Recency", f"{f['recency']:.2f}", f"mean of 0.5 ^ (age / {digest['half_life_days']} days) over dated signals"),
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
    r = sub.add_parser("render", help="validate notes and write digest.md")
    r.add_argument("--run", default="run")
    r.add_argument("--notes", help='notes.json: {"notes": {"<id>": {"title", "summary"}}}')
    args = ap.parse_args(argv)
    try:
        return build(args) if args.cmd == "build" else render(args)
    except signals.Refused as e:
        print(f"digest: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
