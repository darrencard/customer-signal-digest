"""The `signals` key as one self-contained HTML page, in the Leader Report style guide and the Landing Loop's one
visual family, and its Markdown twin.

The page takes the report's whole stylesheet from its template (assets/vendor/template.html, vendored unchanged at a
pinned commit) and draws its picture with svgkit (scripts/vendor/svgkit.py, vendored byte-identical from
landing-loop). Only a few rules for this page's layout are added.

It reads top down for someone who has never seen the loop: the shared header, the verdict as the heading, the
project's status beside this skill's own check, then one scorecard frame in the grammar of the /update outcome
scorecard (svgkit 1.2.0): two rows, customers who still feel the problem and customers who say it is gone, each a
share bar of that side's signals with the last 30 days in ink, `7 accounts · 5 of 7 signals in 30 days`, and the
check word on the problem row. Geist Mono 12px for labels, figures and words, Geist 14px for names, no text inside
any picture. One next step follows, owned by the person the landing brief
names. The quotes and the figures sit in two columns; other themes and everything technical (the ledger, file names,
the record key) fold away. Public copy uses plain words: project, target, the project file.

Colour means one thing each: green, grey-white and red only inside the printed status word, copied from
`landed.status`; brass only for the person who decides. The check prints in ink. The picture draws only figures the
page prints, and its aria-label states the answer.

Every string from a source is escaped. Nothing is loaded from the network, and nothing depends on the clock or the
machine, so the same key gives the same bytes.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import datetime
import html
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))

import svgkit as sk  # noqa: E402  (vendored, unchanged; see VENDORED.json)

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
STYLE = re.compile(r"<style>(.*?)</style>", re.S)
NEXT_STEP_DAYS = 14

# Layout for this page only. Everything else comes from the template's stylesheet and svgkit.CSS.
# In the scorecard the figure column prints in one case, numerals and capitals ("7 ACCOUNTS"), as /update does.
PAGE_CSS = """
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{min-height:0;padding-top:40px;padding-bottom:48px;justify-content:flex-start}
.solo h1{font-size:clamp(34px,4.6vw,60px);line-height:1;letter-spacing:-.04em;text-wrap:balance;margin-bottom:20px}
.solo .lede{margin-bottom:24px}
.solo .lede b{color:var(--t1);font-weight:500}
.solo h2{margin-bottom:16px}
.marks{display:flex;flex-wrap:wrap;align-items:center;gap:10px 28px;margin:0 0 20px;font:400 11px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.marks>span{display:inline-flex;align-items:center;gap:10px}
.chk{font:400 12px/16px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--t1);white-space:nowrap}
.next{margin-top:28px;display:grid;grid-template-columns:200px minmax(0,1fr);gap:8px 32px;align-items:baseline;border:1px solid var(--brass);border-radius:12px;padding:20px 24px;background:var(--brass-bg)}
.next>b{font:400 11px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--brass)}
.next p{margin:0;font-size:16px;line-height:1.5;color:var(--t1)}
.next .who{display:flex;flex-wrap:wrap;gap:4px 24px;margin-top:10px;font:400 11.5px/16px var(--mono);color:var(--brass)}
.next .who span::before{font-size:11px;letter-spacing:.1em;color:var(--t3);margin-right:8px}
.next .who .o::before{content:"DECIDES"}.next .who .d::before{content:"DUE"}
.cols{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:24px 56px;align-items:start}
.cols h3{margin-bottom:8px}
.figs{margin:0;display:grid}
.figs>div{display:grid;grid-template-columns:132px minmax(0,1fr);gap:4px 16px;border-top:1px solid var(--line);padding:11px 0}
.figs dt{font:400 11px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.figs dd{margin:0;font-size:13.5px;line-height:1.55;color:var(--t2)}
.figs dd b{color:var(--t1);font-weight:500}
.theme{margin:0 0 28px}
.theme .side{font:400 11px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.theme h4{margin:4px 0;font-size:16px;font-weight:500;color:var(--t1)}
.theme .sum{margin:0 0 6px;font-size:13px;color:var(--t2)}
.q{margin:0;padding:12px 0;border-top:1px solid var(--line)}
.q p{margin:0 0 6px;font-size:14px;line-height:1.55;color:var(--t1)}
.q footer{display:flex;flex-wrap:wrap;align-items:center;gap:6px 16px;font:400 11px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.talk{margin:8px 0 0;font:400 11px/18px var(--mono);color:var(--t3)}
.solo details{margin-top:4px}
.solo details>*:not(summary){margin-top:12px}
.solo details p,.solo details li{margin:0 0 10px;font-size:13px;color:var(--t2)}
.solo details ul{padding-left:18px}
.tablewrap td,.tablewrap th{overflow-wrap:anywhere}
.nw{white-space:nowrap}
::selection{background:var(--t1);color:var(--bg)}
:focus-visible{outline-color:var(--t1)}
.foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:980px){.foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:24px}.cols,.next{grid-template-columns:1fr}
.stack table,.stack tbody,.stack tr,.stack td{display:block}.stack tr:first-child{display:none}.stack tr{padding:10px 16px;border-bottom:1px solid var(--line)}
.stack td{border:0;padding:3px 0;display:grid;grid-template-columns:118px 1fr;gap:12px}.stack td.num{text-align:left;white-space:normal}
.stack td::before{content:attr(data-l);font:400 11px/20px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}}
@media (max-width:560px){.figs>div{grid-template-columns:1fr;gap:0}}
.scg .sc-l{text-transform:uppercase;letter-spacing:.06em}
/* Full column (site rule since 2026-11-25): every title and text block runs the content column, the scorecard frame's width. */
.solo h1,.solo h2,.solo h3,.solo .lede,.solo .next,.solo p,.solo li,.solo .sk figcaption{max-width:none}
.solo h1{text-wrap:balance}.solo .lede,.solo p,.solo li,.solo .sk figcaption{text-wrap:pretty}
"""

SIDE_LABEL = {"problem": "Still feel the problem", "praise": "Problem gone"}
CHECK_PLAIN = {"problem still raised": "problem still raised", "problem not raised": "problem not raised", None: "not checked"}

# The record's own sentences, in the page's words. The record keeps its words.
WORDS = (
    (r"\bthe bets\b", "the projects"),
    (r"\bthe bet\b", "the project"),
    (r"\bbet\b", "project"),
    (r"\bthe brief's bar\b", "the landing brief's target"),
    (r"\bthemes\.json\b", "the theme list"),
)


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def accounts_text(ids: list[str]) -> str:
    """Account ids as the page prints them: "account 9010, account 9003"."""
    return ", ".join(f"account {a}" for a in ids)


def plain(text: str) -> str:
    text = re.sub(r"highest ARR first \(([^)]*)\)", lambda m: f"highest revenue first ({accounts_text(m.group(1).split(', '))})", text)
    for pattern, to in WORDS:
        text = re.sub(pattern, to, text)
    return text


FONT_FLOOR = 12  # px: no text on the page renders smaller, at any width
FONT_SIZE = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)px")
FONT_SHORTHAND = re.compile(r"(font\s*:[^;{}]*?)(?<![\w.-])(\d+(?:\.\d+)?)px")


def floor_fonts(css: str) -> str:
    """Raise every font size under 12px to 12px. The vendored template and svgkit stay byte-identical on disk;
    the floor applies to their text as the page is built, so this page's CSS has no smaller size anywhere."""

    def up(m: re.Match[str]) -> str:
        return f"{m.group(1)}{FONT_FLOOR if float(m.group(2)) < FONT_FLOOR else m.group(2)}px"

    return FONT_SHORTHAND.sub(up, FONT_SIZE.sub(up, css))


ISO_DATE = re.compile(r"(?<![\w-])\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?Z?)?(?![\w-])")


def keep_dates(page: str) -> str:
    """Every ISO date in the page's text held on one line, so a heading never breaks one at a hyphen at any width."""
    head, sep, body = page.partition("<body>")
    return head + sep + re.sub(r">([^<]+)<", lambda m: ">" + ISO_DATE.sub(r'<span class="nw">\g<0></span>', m.group(1)) + "<", body)


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


def plural(count: int, noun: str) -> str:
    return f"{count:,} {noun}{'' if count == 1 else 's'}"


def project_name(bet: str) -> str:
    return bet.replace("-", " ").capitalize()


def status_mark(bs: dict[str, Any]) -> str:
    """The project's status, printed from landed.status as the template draws it. The word always prints."""
    if bs["status"] is None:
        return '<span class="st watch" style="color:var(--t3)">not read</span>'
    return f'<span class="st {e(bs["status"])}">{e(bs["status"])}</span>'


def check_mark(key: dict[str, Any]) -> str:
    """This skill's own check word, as plain mono text in ink: never a boxed chip, never a status colour."""
    return f'<span class="chk">{e(CHECK_PLAIN.get(key["check"], key["check"]))}</span>'


def side(key: dict[str, Any], name: str) -> dict[str, int]:
    """One side's counts: the side totals the key holds, and the last 30 days summed from that side's themes."""
    f = key["figures"]
    themes = [t for t in key["themes"] if t["side"] == name]
    return {
        "signals": f[f"{name}_signals"]["value"],
        "accounts": f[f"{name}_accounts"]["value"],
        "recent": sum(t["figures"]["last_30_days"]["value"] for t in themes),
    }


# The scorecard


def answer(key: dict[str, Any]) -> str:
    """The aria-label: what customers say, and the check, in one sentence each."""
    p, g = side(key, "problem"), side(key, "praise")
    return (
        f"{plural(p['signals'], 'signal')} from {plural(p['accounts'], 'account')} say customers still feel the problem, "
        f"{p['recent']} in the last 30 days; {plural(g['signals'], 'signal')} from {plural(g['accounts'], 'account')} say it is gone, "
        f"{g['recent']} in the last 30 days. {CHECK_PLAIN.get(key['check'], key['check']).capitalize()}."
    )


def check_word(key: dict[str, Any]) -> str:
    """The contract's check word, as text: problem still raised in ink, problem not raised muted."""
    word = CHECK_PLAIN.get(key["check"], key["check"])
    return sk.check_word(word.upper(), ink=key["check"] == "problem still raised")


def scorecard(key: dict[str, Any]) -> str:
    """Two rows: customers who still feel the problem, then customers who say it is gone. Each is a share bar of that
    side's signals, the last 30 days in ink; the figure prints `7 accounts · 5 of 7 signals in 30 days`. The check word
    sits on the problem row, the side it is read from."""
    rows = []
    for name in ("problem", "praise"):
        s = side(key, name)
        figure = sk.figure_line(plural(s["accounts"], "account"), tail=f"{s['recent']} of {plural(s['signals'], 'signal')} in 30 days")
        word = check_word(key) if name == "problem" else ""
        rows.append(sk.sc_row(SIDE_LABEL[name], picture=sk.share_bar(s["recent"], s["signals"]), figure=figure, word=word))
    return sk.sc_frame(
        rows,
        label=answer(key),
        title="Signals about this project",
        head=["Customers", "", "Accounts · last 30 days", "Check"],
        legend=sk.legend("actual", "last 30 days"),
        caption=caption(key),
        illustrative=key["illustrative"],
    )


# The words


def heading(key: dict[str, Any], bet: str) -> str:
    """The verdict: the project's status as did-it-land wrote it, then what customers say."""
    status = key["bet_status"]["status"]
    says = {"landed": "landed", "watch": "is on watch", "stalled": "stalled", None: "has no status yet"}[status]
    p = side(key, "problem")
    if key["check"] == "problem still raised":
        joint = "but" if status == "landed" else "and"
        who = f"{p['accounts']} customer account{' still raises' if p['accounts'] == 1 else 's still raise'} the problem"
        return f"{project_name(bet)} {says}, {joint} {who}."
    if key["check"] == "problem not raised":
        joint = "and" if status == "landed" else "but"
        return f"{project_name(bet)} {says}, {joint} no customer raised the problem in the last 30 days."
    return f"{project_name(bet)} {says}. No customer theme is tied to its problem yet."


def lede(key: dict[str, Any], bet: str) -> str:
    """Who this is about and what was read, defined once: project, landing brief, signal. Returns HTML."""
    b, f = key["brief"], key["figures"]
    return (
        f"{e(project_name(bet))} is a project you expect to move a number. Its <b>landing brief</b>, a one-page plan (what good looks like, "
        f"by when, at what cost), names the problem: {e(b['problem'])} "
        f"This page reads {n(f['signals'])} signals (tickets, chats, call notes and survey comments) from {n(f['accounts'])} customer accounts, "
        f"{e(key['window']['from'])} to {e(key['window']['to'])}."
    )


def caption(key: dict[str, Any]) -> str:
    return f"Each row is one side's signals about this project; the ink share came in the last 30 days, to {key['window']['to']}."


def due_date(as_of: str, by: str | None) -> str:
    """The brief's date while it is ahead of the read; else NEXT_STEP_DAYS after it."""
    day = datetime.date.fromisoformat(as_of[:10])
    if by and datetime.date.fromisoformat(by) > day:
        return by
    return str(day + datetime.timedelta(days=NEXT_STEP_DAYS))


def figures(key: dict[str, Any]) -> list[tuple[str, str]]:
    """The figures column, label then HTML. Every number is a figure in the key, or a sum of theme figures."""
    b, f, bs = key["brief"], key["figures"], key["bet_status"]
    p, g = side(key, "problem"), side(key, "praise")
    better = "or higher" if b["better"] == "higher" else "or lower"
    cur = bs.get("current")
    if bs["status"] is None:
        now = "Not read yet: run Did it land?"
    elif cur:
        now = f"<b>{e(n(cur))}</b> on {e(cur['window']['to'])}, in the Did it land? read."
    else:
        now = "From the Did it land? read."
    return [
        ("The target", f"{e(b['metric'])}: <b>{e(b['bar'])}</b> {better} by {e(b['by'])}."),
        ("The number now", now),
        (
            "Still feel it",
            f"<b>{plural(p['signals'], 'signal')}</b> from {plural(p['accounts'], 'account')}: {n(f['problem_last_30_days'])} in the last 30 days, "
            f"{n(f['problem_prior_30_days'])} in the 30 days before.",
        ),
        ("Problem gone", f"<b>{plural(g['signals'], 'signal')}</b> from {plural(g['accounts'], 'account')}: {g['recent']} in the last 30 days."),
        (
            "All feedback",
            f"{n(f['signals'])} signals from {n(f['accounts'])} accounts, {e(key['window']['from'])} to {e(key['window']['to'])}. {n(f['on_bet_share'])} are about this project.",
        ),
        (
            "Cleaned first",
            f"{plural(key['duplicates_merged']['value'], 'duplicate')} merged. {plural(key['redacted_spans']['value'], 'piece')} of personal data removed before anything was read.",
        ),
    ]


def theme_block(t: dict[str, Any], ill: bool) -> str:
    f = t["figures"]
    tag = '<span class="sk-ill">Illustrative</span>' if ill else ""
    quotes = "".join(f'<blockquote class="q"><p>&ldquo;{e(q["text"])}&rdquo;</p><footer><span>{e(q["created"])}</span>{tag}</footer></blockquote>' for q in t["quotes"])
    talk = f'<p class="talk">Accounts to talk to, highest revenue first: {e(accounts_text(t["talk_to"]))}</p>' if t["talk_to"] and t["side"] == "problem" else ""
    summary = (
        f"{plural(f['signals']['value'], 'signal')} from {plural(f['accounts']['value'], 'account')}; {n(f['last_30_days'])} in the last 30 days, "
        f"{n(f['prior_30_days'])} in the 30 days before."
    )
    return f'<div class="theme"><span class="side">{e(SIDE_LABEL.get(t["side"], "Other"))}</span><h4>{e(t["name"])}</h4><p class="sum">{e(summary)}</p>{quotes}{talk}</div>'


class Table:
    """A table whose cells carry their column name, so a phone shows each row as labelled lines."""

    def __init__(self, heads: tuple[str, ...]) -> None:
        self.heads = heads
        self.rows: list[str] = []

    def row(self, *cells: tuple[str, str]) -> None:
        tds = []
        for head, (cls, body) in zip(self.heads, cells, strict=True):
            attr = f' class="{cls}"' if cls else ""
            tds.append(f'<td{attr} data-l="{e(head)}">{body}</td>')
        self.rows.append("<tr>" + "".join(tds) + "</tr>")

    def html(self) -> str:
        head = "<tr>" + "".join(f"<th>{e(h)}</th>" for h in self.heads) + "</tr>"
        return f'<div class="tablewrap stack"><table>{head}{"".join(self.rows)}</table></div>'


def others_table(themes: list[dict[str, Any]]) -> str:
    tab = Table(("Theme", "Accounts", "Signals", "Last 30 days", "30 days before"))
    for t in themes:
        f = t["figures"]
        tab.row(("", e(t["name"])), *(("num", n(f[k])) for k in ("accounts", "signals", "last_30_days", "prior_30_days")))
    return tab.html()


def how(fg: dict[str, Any]) -> str:
    """The part of a figure's source that says how it was computed; the inputs are listed once below the ledger."""
    return fg["source"].split(";")[0].split(": ", 1)[-1]


def ledger(key: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out = [(name, f) for name, f in key["figures"].items()]
    out += [("duplicates_merged", key["duplicates_merged"]), ("redacted_spans", key["redacted_spans"])]
    return out


def fold(title: str, body: str) -> str:
    return f"<details><summary>{e(title)}</summary>{body}</details>"


def quote_ids(t: dict[str, Any]) -> str:
    return ", ".join(i for q in t["quotes"] for i in q["ids"]) or "none quoted"


def engineers(key: dict[str, Any]) -> str:
    """The ledger, sources, rank, files and the record key: none of it is needed to act on the page."""
    bs = key["bet_status"]
    led = Table(("Figure", "Value", "Unit", "Window", "How"))
    for name, fg in ledger(key):
        led.row(("mono", e(name)), ("num", e(n(fg))), ("", e(fg["unit"])), ("mono nw", f"{e(fg['window']['from'])} to {e(fg['window']['to'])}"), ("", e(how(fg))))
    rank = Table(("Theme", "Side", "Rank", "Quote sources"))
    for t in key["themes"]:
        rank.row(("", e(t["name"])), ("mono", e(t["side"])), ("num", n(t["rank"])), ("mono", e(quote_ids(t))))
    srcs = "".join(f"<li>{e(i['system'])}: {e(', '.join(i['files']))}. {e(i['how'])}; {n(i['signals'])} signals.</li>" for i in key["inputs"])
    left = "".join(f"<li>Left out, {e(k)}: {n(v)}.</li>" for k, v in key["left_out"].items())
    status = f"<code>{e(bs['status'])}</code>, copied from <code>{e(bs['printed_from'])}</code> as {e(bs['computed_by'])} wrote it" if bs["status"] else "not read"
    notes = (
        f"<p>Status: {status}. Check as the record stores it: <code>{e(key['check'] or 'null')}</code>. {e(key['check_reason'])}</p>"
        f"<p>Landing brief: <code>{e(key['brief']['path'])}</code>. Built by {e(key['tool'])}.</p>"
        "<p>With --loop and --bet, the build adds its page to the project file: the <code>signals</code> key of "
        "<code>landing/&lt;bet&gt;.json</code>, and no other key. The status is copied from <code>landed.status</code>, never computed. "
        "Quotes are redacted in code before grouping; redaction is pattern-based, so read the quotes before sharing outside the team.</p>"
    )
    return fold("For your engineers", f"{led.html()}<ul>{srcs}{left}</ul>{rank.html()}{notes}")


def page(key: dict[str, Any], bet: str) -> str:
    bs, ill = key["bet_status"], key["illustrative"]
    title = f"What customers said: {project_name(bet)}"
    version = "v" + key["tool"].rsplit(" ", 1)[-1]
    header = sk.page_header("Customer signals", date=f"As of {key['as_of']}", version=version, illustrative=ill)
    marks = f'<p class="marks"><span>Project status, from Did it land? {status_mark(bs)}</span><span>Customer check {check_mark(key)}</span></p>'
    pic = scorecard(key)
    step = (
        f'<div class="next"><b>What to do next</b><div><p>{e(plain(key["next_step"]))}</p>'
        f'<span class="who"><span class="o">{e(key["decides"])}</span><span class="d">{e(due_date(key["as_of"], key["brief"]["by"]))}</span></span></div></div>'
    )
    cover = f'<section class="slide cover">{header}<h1>{e(heading(key, bet))}</h1><p class="lede">{lede(key, bet)}</p>{marks}{pic}{step}</section>'
    on_bet = [t for t in key["themes"] if t["side"] in ("problem", "praise")]
    figs = '<dl class="figs">' + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in figures(key)) + "</dl>"
    detail = (
        '<section class="slide"><div class="meta"><span>What customers said</span></div><div class="cols">'
        f"<div><h3>In their words</h3>{''.join(theme_block(t, ill) for t in on_bet)}</div><div><h3>The figures</h3>{figs}</div></div></section>"
    )
    others = [t for t in key["themes"] if t["side"] == "other"]
    folds = fold(f"Everything else customers raised ({plural(len(others), 'theme')})", others_table(others)) if others else ""
    more = f'<section class="slide"><div class="meta"><span>Detail</span></div>{folds}{engineers(key)}</section>'
    foot = (
        '<p class="foot">Signals show what customers raised, not why the number moved. Quotes are redacted in code before they are shown'
        + ("; in this sample every quote and figure is invented." if ill else ".")
        + " Every figure is computed in code from the sources named.</p>"
    )
    return keep_dates(
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{floor_fonts(stylesheet() + sk.CSS + sk.SCORECARD_CSS + PAGE_CSS)}</style></head><body><main class="solo">'
        f"{cover}{detail}{more}{foot}</main></body></html>\n"
    )


def _md(text: Any) -> str:
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", str(text))


def _text(fragment: str) -> str:
    """An HTML fragment of this page as plain text."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def markdown(key: dict[str, Any], bet: str) -> str:
    """The plain-text twin of the page: the same figures and words, in the same order."""
    bs = key["bet_status"]
    p, g = side(key, "problem"), side(key, "praise")
    version = key["tool"].rsplit(" ", 1)[-1]
    out = [f"# {_md(heading(key, bet))}", "", f"Customer signals v{version}. As of {key['as_of']}." + (" Illustrative." if key["illustrative"] else ""), ""]
    out += [_md(_text(lede(key, bet))), ""]
    out += [f"**Project status (Did it land?):** {bs['status'] or 'not read'}. **Customer check:** {CHECK_PLAIN.get(key['check'], key['check'])}.", ""]
    out += [
        f"Still feel the problem: {plural(p['signals'], 'signal')} from {plural(p['accounts'], 'account')}, {p['recent']} in the last 30 days. "
        f"Problem gone: {plural(g['signals'], 'signal')} from {plural(g['accounts'], 'account')}, {g['recent']} in the last 30 days.",
        "",
    ]
    out += ["## What to do next", "", _md(plain(key["next_step"])), "", f"Decides: {_md(key['decides'])}. Due: {due_date(key['as_of'], key['brief']['by'])}.", ""]
    out += ["## In their words", ""]
    for t in key["themes"]:
        if t["side"] not in ("problem", "praise"):
            continue
        f = t["figures"]
        out += [
            f"### {_md(t['name'])}",
            "",
            f"{SIDE_LABEL[t['side']]}. {plural(f['signals']['value'], 'signal')} from {plural(f['accounts']['value'], 'account')}; "
            f"{n(f['last_30_days'])} in the last 30 days, {n(f['prior_30_days'])} in the 30 days before.",
            "",
        ]
        for q in t["quotes"]:
            out += [f"> {_md(q['text'])}", f"> ({q['created']}{'; illustrative' if q['illustrative'] else ''})", ""]
        if t["talk_to"] and t["side"] == "problem":
            out += [f"Accounts to talk to, highest revenue first: {accounts_text(t['talk_to'])}", ""]
    out += ["## The figures", ""]
    out += [f"- **{k}:** {_md(_text(v))}" for k, v in figures(key)]
    out += [""]
    others = [t for t in key["themes"] if t["side"] == "other"]
    if others:
        out += ["## Everything else customers raised", "", "| Theme | Accounts | Signals | Last 30 days | 30 days before |", "|---|---|---|---|---|"]
        out += ["| " + " | ".join([_md(t["name"])] + [n(t["figures"][k]) for k in ("accounts", "signals", "last_30_days", "prior_30_days")]) + " |" for t in others]
        out += [""]
    out += ["## For your engineers", "", "| Figure | Value | Unit | Window | How |", "|---|---|---|---|---|"]
    out += [f"| {_md(name)} | {n(fg)} | {fg['unit']} | {fg['window']['from']} to {fg['window']['to']} | {_md(how(fg))} |" for name, fg in ledger(key)]
    out += [""] + [f"- **{_md(i['system'])}:** {_md(', '.join(i['files']))}. {i['how']}; {n(i['signals'])} signals." for i in key["inputs"]]
    out += [f"- **Left out, {_md(k)}:** {n(v)}." for k, v in key["left_out"].items()]
    out += ["", "| Theme | Side | Rank | Quote sources |", "|---|---|---|---|"]
    out += [f"| {_md(t['name'])} | {t['side']} | {n(t['rank'])} | {_md(quote_ids(t))} |" for t in key["themes"]]
    status = f"`{bs['status']}`, copied from `{bs['printed_from']}` as {bs['computed_by']} wrote it" if bs["status"] else "not read"
    out += ["", f"Status: {status}. Check as the record stores it: `{key['check'] or 'null'}`. {_md(key['check_reason'])}", ""]
    out += [
        f"Landing brief: `{key['brief']['path']}`. Built by {key['tool']}. With --loop and --bet, the build adds its page to the project file: "
        "the `signals` key of `landing/<bet>.json`, and no other key.",
        "",
    ]
    return "\n".join(out)
