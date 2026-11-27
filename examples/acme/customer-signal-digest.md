# Quote drafting landed, but 7 customer accounts still raise the problem.

Customer signals v0.3.2. As of 2026-11-26. Illustrative.

Quote drafting is a project you expect to move a number. Its landing brief, a one-page plan (what good looks like, by when, at what cost), names the problem: Tradespeople spend evenings writing quotes by hand, so quotes go out late and lose the job. This page reads 21 signals (tickets, chats, call notes and survey comments) from 16 customer accounts, 2026-09-07 to 2026-11-24.

**Project status (Did it land?):** landed. **Customer check:** problem still raised.

Still feel the problem: 7 signals from 7 accounts, 5 in the last 30 days. Problem gone: 5 signals from 5 accounts, 2 in the last 30 days.

## What to do next

Talk to the 7 accounts on the problem side, highest revenue first (account 9010, account 9003, account 9001, account 9007, account 9012, account 9005, account 9008), before deciding whether to scale the project.

Decides: Head of Product, Quoting squad. Due: 2026-12-10.

## In their words

### Quote drafts miss line items

Still feel the problem. 7 signals from 7 accounts; 5 in the last 30 days, 2 in the 30 days before.

> Quote drafts keep missing line items. I check every one by hand now.
> (2026-11-21; illustrative)

> The quote draft left off the materials for the boiler swap. Copper pipe and fittings were missing.
> (2026-11-20; illustrative)

> Spoke with \[NAME\]. Their estimators stopped using AI quote drafts because line items for materials go missing. They re-key every quote.
> (2026-11-19; illustrative)

Accounts to talk to, highest revenue first: account 9010, account 9003, account 9001, account 9007, account 9012, account 9005, account 9008

### Quotes go out the same day

Problem gone. 5 signals from 5 accounts; 2 in the last 30 days, 2 in the 30 days before.

> Love that quotes go out the same day now. Customers notice.
> (2026-11-16; illustrative)

> Drafting a quote takes minutes now, not my evenings.
> (2026-11-09; illustrative)

> Quotes go out the same day now. Got my evenings back.
> (2026-10-20; illustrative)

## The figures

- **The target:** Quote draft acceptance rate: 40% or higher by 2026-11-15.
- **The number now:** 43% on 2026-11-23, in the Did it land? read.
- **Still feel it:** 7 signals from 7 accounts: 5 in the last 30 days, 2 in the 30 days before.
- **Problem gone:** 5 signals from 5 accounts: 2 in the last 30 days.
- **All feedback:** 21 signals from 16 accounts, 2026-09-07 to 2026-11-24. 57.1% are about this project.
- **Cleaned first:** 2 duplicates merged. 16 pieces of personal data removed before anything was read.

## Everything else customers raised

| Theme | Accounts | Signals | Last 30 days | 30 days before |
|---|---|---|---|---|
| Invoice chasers go to customers who already paid | 4 | 4 | 4 | 0 |
| Mobile app loses job notes offline | 2 | 2 | 1 | 1 |
| Accounting export puts the wrong tax code on labour | 1 | 2 | 1 | 1 |
| Unnamed: app, dark, early | 1 | 1 | 0 | 0 |

## For your engineers

| Figure | Value | Unit | Window | How |
|---|---|---|---|---|
| signals | 21 | signals | 2026-09-07 to 2026-11-24 | signals in the window after duplicates were merged |
| accounts | 16 | accounts | 2026-09-07 to 2026-11-24 | distinct accounts named on those signals |
| on\_bet\_signals | 12 | signals | 2026-09-07 to 2026-11-24 | signals in themes tied to quote-drafting |
| on\_bet\_share | 57.1% | % | 2026-09-07 to 2026-11-24 | signals in themes tied to quote-drafting / all signals |
| problem\_signals | 7 | signals | 2026-09-07 to 2026-11-24 | signals in themes on the problem side |
| problem\_accounts | 7 | accounts | 2026-09-07 to 2026-11-24 | distinct accounts on the problem side |
| problem\_last\_30\_days | 5 | signals | 2026-10-28 to 2026-11-24 | problem-side signals in the last 30 days |
| problem\_prior\_30\_days | 2 | signals | 2026-09-28 to 2026-10-27 | problem-side signals in the 30 days before |
| praise\_signals | 5 | signals | 2026-09-07 to 2026-11-24 | signals in themes on the praise side |
| praise\_accounts | 5 | accounts | 2026-09-07 to 2026-11-24 | distinct accounts on the praise side |
| duplicates\_merged | 2 | signals | 2026-09-07 to 2026-11-24 | signals merged into another as the same complaint |
| redacted\_spans | 16 | spans | 2026-09-07 to 2026-11-24 | personal-data spans replaced before grouping |

- **Zendesk:** zendesk-page-1.json, zendesk-page-2.json. Live: API pages saved as returned; 9 signals.
- **Intercom:** intercom-conversations.json. Live: API pages saved as returned; 4 signals.
- **CSV (calls):** calls.csv. CSV fallback; 5 signals.
- **CSV (nps):** nps.csv. CSV fallback; 7 signals.
- **Left out, nps rows with no text:** 1.
- **Left out, signals before 2026-09-07 or undated:** 1.
- **Left out, signals after 2026-11-24:** 1.

| Theme | Side | Rank | Quote sources |
|---|---|---|---|
| Quote drafts miss line items | problem | 1 | nps:N-01, intercom:215001, zendesk:4101, calls:C-301 |
| Quotes go out the same day | praise | 2 | intercom:215006, nps:N-08, nps:N-07 |
| Invoice chasers go to customers who already paid | other | 3 | nps:N-04, zendesk:4102, intercom:215004 |
| Mobile app loses job notes offline | other | 4 | nps:N-03, zendesk:4105 |
| Accounting export puts the wrong tax code on labour | other | 5 | calls:C-302, zendesk:4104 |
| Unnamed: app, dark, early | other | 6 | zendesk:4106 |

Status: `landed`, copied from `landed.status` as did-it-land 0.3.2 wrote it. Check as the record stores it: `problem still raised`. 7 signals from 7 accounts say the problem is still there, 5 of them in the last 30 days.

Landing brief: `quote-drafting.md`. Built by customer-signal-digest 0.3.2. With --loop and --bet, the build adds its page to the project file: the `signals` key of `landing/<bet>.json`, and no other key.
