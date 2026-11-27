# What customers said: Quote drafting

As of 2026-11-26. customer-signal-digest 0.3.0. Illustrative.

7 signals from 7 accounts say the problem is still there, 5 of them in the last 30 days. 5 signals from 5 accounts say it is gone. In all, 21 signals from 16 accounts, 2026-09-07 to 2026-11-24; 57.1% are about quote drafting.

## The bet against its brief

- **Problem:** Tradespeople spend evenings writing quotes by hand, so quotes go out late and lose the job.
- **Bar:** Quote draft acceptance rate: 40%, higher is better, by 2026-11-15.
- **Bet status:** landed. Printed from landed.status, as did-it-land 0.3.0 wrote it. Quote draft acceptance rate is 43% (2026-11-23).
- **Signal check:** problem still raised. 7 signals from 7 accounts say the problem is still there, 5 of them in the last 30 days.

## In their words

### Quote drafts miss line items

The problem, still there. Rank 1. 7 signals, 7 accounts, 5 in the last 30 days, 2 in the 30 days before.

> Quote drafts keep missing line items. I check every one by hand now.
> (2026-11-21; nps:N-01; illustrative)

> The quote draft left off the materials for the boiler swap. Copper pipe and fittings were missing.
> (2026-11-20; intercom:215001, zendesk:4101; illustrative)

> Spoke with \[NAME\]. Their estimators stopped using AI quote drafts because line items for materials go missing. They re-key every quote.
> (2026-11-19; calls:C-301; illustrative)

Accounts to talk to, highest ARR first: 9010, 9003, 9001, 9007, 9012, 9005, 9008

### Quotes go out the same day

The problem, gone. Rank 2. 5 signals, 5 accounts, 2 in the last 30 days, 2 in the 30 days before.

> Love that quotes go out the same day now. Customers notice.
> (2026-11-16; intercom:215006; illustrative)

> Drafting a quote takes minutes now, not my evenings.
> (2026-11-09; nps:N-08; illustrative)

> Quotes go out the same day now. Got my evenings back.
> (2026-10-20; nps:N-07; illustrative)

## Other themes, ranked

| Theme | Rank | Accounts | Signals | Last 30 days | 30 days before |
|---|---|---|---|---|---|
| Invoice chasers go to customers who already paid | 3 | 4 | 4 | 4 | 0 |
| Mobile app loses job notes offline | 4 | 2 | 2 | 1 | 1 |
| Accounting export puts the wrong tax code on labour | 5 | 1 | 2 | 1 | 1 |
| Unnamed: app, dark, early | 6 | 1 | 1 | 0 | 0 |

## Evidence ledger

| Figure | Value | Unit | Window | How |
|---|---|---|---|---|
| signals | 21 | signals | 2026-09-07 to 2026-11-24 | signals in the window after duplicates were merged |
| accounts | 16 | accounts | 2026-09-07 to 2026-11-24 | distinct accounts named on those signals |
| on_bet_signals | 12 | signals | 2026-09-07 to 2026-11-24 | signals in themes tied to quote-drafting |
| on_bet_share | 57.1% | % | 2026-09-07 to 2026-11-24 | signals in themes tied to quote-drafting / all signals |
| problem_signals | 7 | signals | 2026-09-07 to 2026-11-24 | signals in themes on the problem side |
| problem_accounts | 7 | accounts | 2026-09-07 to 2026-11-24 | distinct accounts on the problem side |
| problem_last_30_days | 5 | signals | 2026-10-28 to 2026-11-24 | problem-side signals in the last 30 days |
| problem_prior_30_days | 2 | signals | 2026-09-28 to 2026-10-27 | problem-side signals in the 30 days before |
| praise_signals | 5 | signals | 2026-09-07 to 2026-11-24 | signals in themes on the praise side |
| praise_accounts | 5 | accounts | 2026-09-07 to 2026-11-24 | distinct accounts on the praise side |
| duplicates_merged | 2 | signals | 2026-09-07 to 2026-11-24 | signals merged into another as the same complaint |
| redacted_spans | 16 | spans | 2026-09-07 to 2026-11-24 | personal-data spans replaced before grouping |

- **Zendesk:** zendesk-page-1.json, zendesk-page-2.json. Live: API pages saved as returned.
- **Intercom:** intercom-conversations.json. Live: API pages saved as returned.
- **CSV (calls):** calls.csv. CSV fallback.
- **CSV (nps):** nps.csv. CSV fallback.
- **Left out:** nps rows with no text: 1; signals before 2026-09-07 or undated: 1; signals after 2026-11-24: 1.

**Next step:** Talk to the 7 accounts on the problem side, highest ARR first (9010, 9003, 9001, 9007, 9012, 9005, 9008), before deciding whether to scale the bet. Decides: Head of Product, Quoting squad.
