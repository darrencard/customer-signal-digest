"""The `signals` key as one self-contained HTML page in the Leader Report style guide, and its Markdown twin.

The page takes the report's whole stylesheet from its template (assets/vendor/template.html, vendored unchanged at a
pinned commit), so it is the same brand family as the deck. It follows the report's references/design.md: mono
capitals for labels, sans for sentences; hairlines, not boxes; green, grey-white and red for the bet's status only,
printed from `landed.status` with the word beside it; brass only for the person who decides; the illustrative
tag visible on every quote when the data is a sample.

Every string from a source is escaped. Nothing is loaded from the network, and nothing depends on the clock or the
machine, so the same key gives the same bytes.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
STYLE = re.compile(r"<style>(.*?)</style>", re.S)

PAGE_CSS = """
/* The vendored template paints selection and focus green; green is kept for landed, so both print in ink here. */
::selection{background:var(--t1);color:var(--bg)}
:focus-visible{outline-color:var(--t1)}
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{padding-top:72px;padding-bottom:40px}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:10px 24px}
.head h2{margin-bottom:12px}
.rows{margin-top:8px}
.rows>div{display:grid;grid-template-columns:168px minmax(0,1fr);gap:6px 36px;border-top:1px solid var(--line);padding:14px 0}
.rows>div>span:first-child{font:400 10px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.rows>div>span:last-child{color:var(--t2);font-size:13.5px}
.nw{white-space:nowrap}
.chk{font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t1);border:1px solid var(--line3);border-radius:3px;padding:2px 7px;white-space:nowrap}
.q{margin:0;padding:14px 0;border-top:1px solid var(--line)}
.q p{margin:0 0 6px;font-size:14px;line-height:1.55;color:var(--t1)}
.q footer{display:flex;flex-wrap:wrap;gap:6px 16px;font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.theme{margin-top:28px}
.theme h3{margin:0 0 4px;font-size:16px}
.theme .facts{margin-top:12px;padding-top:12px}
.solo .need{margin-top:28px}
.solo .need-r{margin-top:0}
.foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:980px){.rows>div{grid-template-columns:1fr;gap:2px}.foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:48px}}
"""

MARK = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">'
    '<rect x="2" y="13" width="3" height="7" fill="var(--agent)"/><rect x="7" y="10" width="3" height="10" fill="var(--agent)"/>'
    '<rect x="12" y="2" width="1.5" height="20" fill="var(--brass)"/><rect x="16" y="4" width="4" height="16" fill="var(--t1)"/></svg>'
)
SIDE_LABEL = {"problem": "The problem, still there", "praise": "The problem, gone"}


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def stylesheet() -> str:
    try:
        found = STYLE.search(TEMPLATE.read_text(encoding="utf-8"))
    except OSError:
        found = None
    return found.group(1) if found else ""


def n(f: dict[str, Any]) -> str:
    """A figure as printed: whole numbers with separators, shares to one decimal place."""
    v = f["value"]
    if f["unit"] == "%":
        return f"{v:g}%"
    if f["unit"] == "ARR":
        return f"{v:,.0f}"
    return f"{v:,}" if isinstance(v, int) else f"{v:,g}"


def status_mark(bs: dict[str, Any]) -> str:
    """The bet's status, printed from landed.status as the template draws it. The word always prints."""
    if bs["status"] is None:
        return '<span class="st watch" style="color:var(--t3)">not read</span>'
    return f'<span class="st {e(bs["status"])}">{e(bs["status"])}</span>'


def check_mark(key: dict[str, Any]) -> str:
    """This skill's own check word. Ink on a hairline: never a status colour."""
    return f'<span class="chk">{e(key["check"] or "not checked")}</span>'


def status_text(bs: dict[str, Any]) -> str:
    if bs["status"] is None:
        return "Not read yet: run did-it-land."
    cur = bs.get("current")
    now = f" {bs.get('metric', 'The metric')} is {n(cur)} ({cur['window']['to']})." if cur else ""
    return f"Printed from {bs['printed_from']}, as {bs['computed_by']} wrote it.{now}"


def facts(items: list[tuple[str, str]]) -> str:
    return '<div class="facts">' + "".join(f"<span><b>{e(v)}</b>{e(k)}</span>" for k, v in items) + "</div>"


def theme_block(t: dict[str, Any], ill: bool) -> str:
    f = t["figures"]
    tiles = [("Signals", n(f["signals"])), ("Accounts", n(f["accounts"])), ("Last 30 days", n(f["last_30_days"])), ("30 days before", n(f["prior_30_days"]))]
    tag = '<span class="ill">Illustrative</span>' if ill else ""
    quotes = "".join(
        f'<blockquote class="q"><p>&ldquo;{e(q["text"])}&rdquo;</p><footer><span>{e(q["created"])}</span><span>{e(", ".join(q["ids"]))}</span>{tag}</footer></blockquote>'
        for q in t["quotes"]
    )
    talk = (
        f'<p class="mono t3" style="font-size:11px;margin-top:10px">Accounts to talk to, highest ARR first: {e(", ".join(t["talk_to"]))}</p>'
        if t["talk_to"] and t["side"] == "problem"
        else ""
    )
    return (
        f'<div class="theme"><div class="meta"><span>{e(SIDE_LABEL.get(t["side"], "Other"))}</span><span>Rank {n(t["rank"])}</span></div>'
        f"<h3>{e(t['name'])}</h3>{facts(tiles)}{quotes}{talk}</div>"
    )


def others_table(themes: list[dict[str, Any]]) -> str:
    rows = "".join(
        f'<tr><td>{e(t["name"])}</td><td class="num">{n(t["rank"])}</td><td class="num">{n(t["figures"]["accounts"])}</td>'
        f'<td class="num">{n(t["figures"]["signals"])}</td><td class="num">{n(t["figures"]["last_30_days"])}</td><td class="num">{n(t["figures"]["prior_30_days"])}</td></tr>'
        for t in themes
    )
    cols = ("Rank", "Accounts", "Signals", "Last 30 days", "30 days before")
    head = "<tr><th>Theme</th>" + "".join(f'<th class="num">{c}</th>' for c in cols) + "</tr>"
    return f'<div class="tablewrap"><table><thead>{head}</thead><tbody>{rows}</tbody></table></div>'


def how(fg: dict[str, Any]) -> str:
    """The part of a figure's source that says how it was computed; the inputs are listed once below the ledger."""
    return fg["source"].split(";")[0].split(": ", 1)[-1]


def ledger(key: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out = [(name, f) for name, f in key["figures"].items()]
    out += [("duplicates_merged", key["duplicates_merged"]), ("redacted_spans", key["redacted_spans"])]
    return out


def lede(key: dict[str, Any], bet_name: str) -> str:
    """The cover sentence: the check's reason first, then the other side, then the base. Every number is a figure in the key."""
    f = key["figures"]
    return (
        f"{key['check_reason']} {f['praise_signals']['value']} signals from {f['praise_accounts']['value']} accounts say it is gone. "
        f"In all, {f['signals']['value']} signals from {f['accounts']['value']} accounts, {key['window']['from']} to {key['window']['to']}; "
        f"{n(f['on_bet_share'])} are about {bet_name}."
    )


def verdicts(key: dict[str, Any]) -> str:
    """The bet's status as did-it-land wrote it, beside this skill's own check. Two marks, two owners."""
    return (
        f'<div class="meta" style="margin-top:18px;gap:10px 28px"><span>Bet status, from did-it-land</span>{status_mark(key["bet_status"])}'
        f"<span>Signal check</span>{check_mark(key)}</div>"
    )


def page(key: dict[str, Any], bet: str) -> str:
    b, bs, f = key["brief"], key["bet_status"], key["figures"]
    title = f"What customers said: {bet.replace('-', ' ').capitalize()}"
    meta = f"<span>As of {e(key['as_of'])}</span><span>{e(key['tool'])}</span>" + ('<span class="ill">Illustrative</span>' if key["illustrative"] else "")
    cover = (
        f'<section class="slide cover"><div class="brand">{MARK}<span translate="no">DACARD</span></div><div class="meta">{meta}</div>'
        f'<h1>{e(title)}</h1>{verdicts(key)}<p class="lede">{e(lede(key, bet.replace("-", " ")))}</p>'
        + facts(
            [("Signals", n(f["signals"])), ("Accounts", n(f["accounts"])), ("About the bet", n(f["on_bet_share"])), ("Problem side, last 30 days", n(f["problem_last_30_days"]))]
        )
        + "</section>"
    )
    rows = [
        ("Problem", b["problem"]),
        ("Bar", f"{b['metric']}: {b['bar']}, {b['better']} is better, by {b['by']}."),
    ]
    body = "".join(f"<div><span>{e(k)}</span><span>{e(v)}</span></div>" for k, v in rows)
    body += f"<div><span>Bet status</span><span>{status_mark(bs)} &nbsp;{e(status_text(bs))}</span></div>"
    body += f"<div><span>Signal check</span><span>{check_mark(key)} &nbsp;{e(key['check_reason'])}</span></div>"
    bet_section = (
        f'<section class="slide"><div class="meta"><span>The bet against its brief</span><span>{e(b["path"])}</span></div>'
        f'<div class="head"><h2>Did customers feel it?</h2>{check_mark(key)}</div><div class="rows">{body}</div></section>'
    )
    on_bet = [t for t in key["themes"] if t["side"] in ("problem", "praise")]
    others = [t for t in key["themes"] if t["side"] == "other"]
    voices = (
        '<section class="slide"><div class="meta"><span>What they said about the bet</span></div><h2>In their words</h2>'
        + "".join(theme_block(t, key["illustrative"]) for t in on_bet)
        + "</section>"
    )
    rest = f'<section class="slide"><div class="meta"><span>Everything else</span></div><h2>Other themes, ranked</h2>{others_table(others)}</section>' if others else ""
    call = (
        f'<div class="need"><b>Next step</b><div class="need-r"><p>{e(key["next_step"])}</p>'
        f'<span class="mono" style="color:var(--brass);font-size:11px">Decides: {e(key["decides"])}</span></div></div>'
    )
    led_rows = "".join(
        f'<tr><td>{e(name)}</td><td class="num">{e(n(fg))}</td><td>{e(fg["unit"])}</td>'
        f'<td class="mono nw">{e(fg["window"]["from"])} to {e(fg["window"]["to"])}</td><td>{e(how(fg))}</td></tr>'
        for name, fg in ledger(key)
    )
    srcs = "".join(f"<div><span>{e(i['system'])}</span><span>{e(', '.join(i['files']))}. {e(i['how'])}.</span></div>" for i in key["inputs"])
    left = "; ".join(f"{k}: {n(v)}" for k, v in key["left_out"].items())
    srcs += f"<div><span>Left out</span><span>{e(left)}.</span></div>" if left else ""
    led = (
        '<section class="slide"><div class="meta"><span>Evidence ledger</span></div><h2>Every figure, with its source</h2>'
        '<div class="tablewrap"><table><thead><tr><th>Figure</th><th class="num">Value</th><th>Unit</th><th>Window</th><th>How</th></tr></thead>'
        f'<tbody>{led_rows}</tbody></table></div><div class="rows" style="margin-top:20px">{srcs}</div>{call}</section>'
    )
    foot = (
        '<p class="foot">Signal counts show what customers raised, not why the metric moved. Quotes are redacted in code before they are shown'
        + ("; in this sample every quote and figure is invented." if key["illustrative"] else ".")
        + " Redaction is pattern-based: read the quotes before sharing outside the team.</p>"
    )
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{stylesheet()}{PAGE_CSS}</style></head><body><main class="solo">'
        f"{cover}{bet_section}{voices}{rest}{led}{foot}</main></body></html>\n"
    )


def _md(text: Any) -> str:
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", str(text))


def markdown(key: dict[str, Any], bet: str) -> str:
    """The plain-text twin of the page: the same figures and words, in the same order."""
    b, bs = key["brief"], key["bet_status"]
    title = f"What customers said: {bet.replace('-', ' ').capitalize()}"
    out = [f"# {title}", "", f"As of {key['as_of']}. {key['tool']}." + (" Illustrative." if key["illustrative"] else ""), ""]
    out += [_md(lede(key, bet.replace("-", " "))), "", "## The bet against its brief", ""]
    out += [f"- **Problem:** {_md(b['problem'])}", f"- **Bar:** {_md(b['metric'])}: {_md(b['bar'])}, {b['better']} is better, by {b['by']}."]
    out += [f"- **Bet status:** {bs['status'] or 'not read'}. {_md(status_text(bs))}", f"- **Signal check:** {key['check'] or 'not checked'}. {_md(key['check_reason'])}", ""]
    out += ["## In their words", ""]
    for t in key["themes"]:
        if t["side"] not in ("problem", "praise"):
            continue
        f = t["figures"]
        out += [
            f"### {_md(t['name'])}",
            "",
            f"{SIDE_LABEL[t['side']]}. Rank {n(t['rank'])}. {n(f['signals'])} signals, {n(f['accounts'])} accounts, "
            f"{n(f['last_30_days'])} in the last 30 days, {n(f['prior_30_days'])} in the 30 days before.",
            "",
        ]
        for q in t["quotes"]:
            out += [f"> {_md(q['text'])}", f"> ({q['created']}; {', '.join(q['ids'])}{'; illustrative' if q['illustrative'] else ''})", ""]
        if t["talk_to"] and t["side"] == "problem":
            out += [f"Accounts to talk to, highest ARR first: {', '.join(t['talk_to'])}", ""]
    others = [t for t in key["themes"] if t["side"] == "other"]
    if others:
        out += ["## Other themes, ranked", "", "| Theme | Rank | Accounts | Signals | Last 30 days | 30 days before |", "|---|---|---|---|---|---|"]
        out += ["| " + " | ".join([_md(t["name"]), n(t["rank"])] + [n(t["figures"][k]) for k in ("accounts", "signals", "last_30_days", "prior_30_days")]) + " |" for t in others]
        out += [""]
    out += ["## Evidence ledger", "", "| Figure | Value | Unit | Window | How |", "|---|---|---|---|---|"]
    out += [f"| {name} | {n(fg)} | {fg['unit']} | {fg['window']['from']} to {fg['window']['to']} | {_md(how(fg))} |" for name, fg in ledger(key)]
    out += [""] + [f"- **{_md(i['system'])}:** {_md(', '.join(i['files']))}. {i['how']}." for i in key["inputs"]]
    left = "; ".join(f"{k}: {n(v)}" for k, v in key["left_out"].items())
    out += [f"- **Left out:** {_md(left)}."] if left else []
    out += ["", f"**Next step:** {_md(key['next_step'])} Decides: {_md(key['decides'])}.", ""]
    return "\n".join(out)
