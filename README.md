# Turn customer signals into ranked opportunities

Customer Signal Digest is a free Claude skill that reads your support tickets, call notes and NPS answers and ranks what customers are asking for, with every claim quoted, sourced and redacted.

**Why it matters:** themes from a model's read of tickets are hard to trust and hard to check. Here code redacts personal data first, merges duplicates and ranks every opportunity by accounts, ARR, frequency and recency. Claude only names what the code found, and a note that overclaims won't render.

## Install: paste one prompt into Claude Code

```text
Install the Customer Signal Digest skill from https://github.com/darrencard/customer-signal-digest and run its tests. Then build a customer signal digest for the last 90 days from my exports: Zendesk ticket pages, Intercom conversations, and any CSVs of call notes, NPS or survey answers in this folder. Ask me only for the as-of date, how each source names the account, and which CSV columns hold the text and any person's name. If I have no exports yet, show me the digest from the bundled Acme sample first.
```

Needs Python 3.9 or later. Standard library only; no network calls.

## What you get

| Feature | What it does |
|---|---|
| Redaction first | Removes emails, phones, card numbers, IBANs, URLs, IPs, postcodes, street addresses and names before anything is grouped, quoted or written |
| Duplicates merged | The same ticket on two pages, a pasted escalation, or one complaint sent by ticket and then by chat counts once; every merged ID stays in the evidence |
| Ranked in code | Score = 0.5 reach + 0.3 frequency + 0.2 recency, with ARR in reach only when every account has one |
| Sensitivity check | Each rank is re-run under 3 other weightings; a wide rank range means the order rests on the weights |
| Trend and follow-up | Signals in the last 30 days against the 30 before, and the accounts to talk to next, highest ARR first |
| Praise kept apart | NPS split into detractors, passives and promoters; praise-only groups rank after every problem |
| Quoted evidence | Up to 3 quotes per opportunity, newest first, one per account, each with its source IDs |
| Checked notes | Blocks invented figures, "all customers" and causal claims, solution titles, quotes not in the evidence, and personal data |
| Evidence ledger | Every figure, how it was computed, and the IDs behind it, plus `opportunities.csv` for a tracker |

## What it looks like

From the Acme sample (illustrative):

| Rank | Rank range | Opportunity | Accounts | ARR | Signals | Last 30 days | Prior 30 days |
|---|---|---|---|---|---|---|---|
| 1 | 1 | AI quote drafts miss line items | 6 | 96,000 | 7 | 7 | 0 |
| 2 | 2 | Invoice chasers go to customers who already paid | 3 | 25,800 | 4 | 4 | 0 |
| 3 | 3 to 4 | Mobile app loses job notes offline | 2 | 20,400 | 3 | 3 | 0 |

> \[NAME\] says quote drafts are still missing line items for labour. Considering going back to the old template.
> (calls:C-304; call, 2026-11-25)

## Inputs

- **Zendesk:** ticket list, search or search export pages, saved as returned. Fetch with `include=users` so requester names are redacted.
- **Intercom:** conversation search pages, saved as returned.
- **CSV:** call notes, NPS or survey answers. You name the columns; nothing is guessed.
- **Accounts (optional):** `account,arr`.
- **Extra terms to redact (optional):** one per line, for staff or customer company names.
- **Themes (optional):** `themes.json`, which Claude drafts and you confirm.

Not sure what an export holds? `digest.py inspect` prints counts, dates and columns, and flags the personal ones, without showing any text.

## Try it on the sample

```bash
python3 skills/customer-signal-digest/scripts/digest.py build --run run --as-of 2026-11-26 --illustrative \
  --zendesk evals/fixtures/acme/zendesk-page-*.json \
  --intercom evals/fixtures/acme/intercom-conversations.json --intercom-account-attribute account_id --theme-prefix "theme:" \
  --csv "source=calls,kind=call,file=evals/fixtures/acme/call-notes.csv,id=call_id,date=date,text=notes,person=contact" \
  --csv "source=nps,kind=nps,file=evals/fixtures/acme/nps.csv,id=response_id,date=submitted_at,text=comment,score=score" \
  --accounts evals/fixtures/acme/accounts.csv --themes evals/fixtures/acme/themes.json
python3 skills/customer-signal-digest/scripts/digest.py render --run run
```

Acme is invented: invoicing software for trades businesses. Every figure from the sample is illustrative.

## Limits

Redaction is pattern-based and can miss an unusual name or format. Read the quotes before sharing a digest outside the team. Signal counts show demand, not cause.

## Tests

```bash
python3 -m unittest discover -s evals -v
```

MIT licensed. Built by [Dacard](https://www.dacard.ai).
