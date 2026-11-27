# Customer Signal Digest: did customers feel it?

```text
Install the customer-signal-digest skill from https://github.com/darrencard/customer-signal-digest: clone it, find a Python 3.11 or later on this machine (macOS python3 is often 3.9), run the tests with it (python -m unittest discover -s evals), and copy skills/customer-signal-digest into ~/.claude/skills/customer-signal-digest. Then digest what customers said about one shipped project: read its project file (landing/<bet>.json) and landing brief, fetch the feedback from the tools connected to this session (Intercom or the Zendesk API first, saved as returned; CSV for call notes, NPS and anything else), ask me only for what you cannot find, and show me the page it writes.
```

A free Claude skill that reads what customers said about a shipped project, against the problem its landing brief (a one-page plan: what good looks like, by when, at what cost) set out to fix.

A bet is a project you expect to move a number; its bar is the target its landing brief sets.

**Why it matters:** a metric can pass its target while customers still describe the old problem. This puts their words beside the project's status, counted in code, with every quote redacted and sourced.

**Where it sits:** step 04 (Learn) of the Landing Loop. It reads the brief and did-it-land's `landed` key, writes only its own `signals` key, and renders one page in the Leader Report style.

## Try it in one minute

Acme is invented: invoicing software for trades businesses. Its quote drafting assistant shipped on 2026-09-07. Every figure and every quote is illustrative.

```bash
python3 examples/acme/sample.py
```

It needs Python 3.11 or later (on macOS, where `python3` is often 3.9, use `python3.12`). It runs in under a second and writes [examples/acme/customer-signal-digest.html](examples/acme/customer-signal-digest.html), its Markdown twin, and the `signals` key of [examples/acme/landing/quote-drafting.json](examples/acme/landing/quote-drafting.json). Feedback window 2026-09-07 to 2026-11-24, as of 2026-11-26. It starts from the landing-loop project file filtered to what this skill reads ([examples/acme/upstream](examples/acme/upstream)). A test checks the command reproduces the committed files byte for byte.

What it finds: the metric landed (43% against a 40% target, as did-it-land wrote it), and the problem is still raised. 7 signals from 7 accounts say quote drafts miss line items, 5 of them in the last 30 days. 5 accounts say quotes now go out the same day.

## Install

As a plugin, in Claude Code:

```text
/plugin marketplace add darrencard/landing-loop
/plugin install customer-signal-digest@landing-loop
```

Standalone: copy `skills/customer-signal-digest` into `~/.claude/skills/`. Python 3.11 or later, standard library only. The scripts make no network calls.

## Reads and writes

| | What |
|---|---|
| Reads | The landing brief, through the Leader Report's own parser (vendored unchanged); `landed` from the project file, `landing/<bet>.json`; customer feedback |
| Feedback, live first | Zendesk ticket pages and Intercom conversation pages as the APIs return them, read with the Leader Report's own page reader (vendored at a pinned commit) |
| Feedback, CSV fallback | Call notes, NPS and survey answers. You name the columns; nothing is guessed |
| Writes | The `signals` key of the project file, nothing else; one HTML page and its Markdown twin |
| Never | Computes a project's status. It prints `landed.status` as did-it-land wrote it |

Its own check has two words: **problem still raised** when a theme tied to the project's problem has a signal in the last 30 days, **problem not raised** when none has. You confirm which themes are about the project (`"bet"` and `"side"` in `themes.json`); code never guesses.

## The project file's key

Every figure carries value, unit, source, window and as_of. Shortened:

```json
"signals": {
  "tool": "customer-signal-digest 0.3.1",
  "as_of": "2026-11-26",
  "window": {"from": "2026-09-07", "to": "2026-11-24"},
  "check": "problem still raised",
  "bet_status": {"status": "landed", "printed_from": "landed.status", "computed_by": "did-it-land 0.3.1"},
  "figures": {
    "problem_last_30_days": {"value": 5, "unit": "signals", "source": "customer-signal-digest 0.3.1: problem-side signals in the last 30 days; Zendesk: ...", "window": {"from": "2026-10-28", "to": "2026-11-24"}, "as_of": "2026-11-26"}
  },
  "themes": [{"id": "quote-line-items", "side": "problem", "quotes": [{"text": "Quote drafts keep missing line items. ...", "ids": ["nps:N-01"], "illustrative": true}]}],
  "next_step": "Talk to the 7 accounts on the problem side, highest ARR first ...",
  "decides": "Head of Product, Quoting squad"
}
```

## Limits

- Signal counts show what customers raised, not why the metric moved.
- Redaction is pattern-based and can miss an unusual name or format. Read the quotes before sharing outside the team.
- Grouping is keywords and word overlap, not meaning. A theme map you confirm does most of the work.
- The Zendesk and Intercom readers are tested on documented response shapes, not yet on a live account.
- Not yet run on a real team's data.

## Go deeper

- [SKILL.md](skills/customer-signal-digest/SKILL.md): the workflow, the inputs, every rule and the notes check.
- Without a project: `digest.py build` and `digest.py render` still rank every theme customers raised, with no project file.
- [CHANGELOG.md](CHANGELOG.md)

MIT licence. Made by [Dacard](https://www.dacard.ai).

Claude and Claude Code are trademarks of Anthropic, PBC. These skills are independent and not affiliated with or endorsed by Anthropic.
