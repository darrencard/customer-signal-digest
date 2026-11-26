#!/usr/bin/env python3
"""Rank opportunities by reach, frequency and recency. Every figure is computed here; nothing is estimated.

Per opportunity:
  signals      deduplicated signals
  mentions     signals plus the duplicates merged into them
  accounts     distinct accounts named on its signals (a signal with no account adds no reach)
  arr          summed ARR of those accounts, when an accounts file gives it
  last_seen    the latest signal date; days_since_last counts from --as-of
  recency      mean over dated signals of 0.5 ** (age in days / half-life). 1.0 is all today; 0.5 is all one half-life old
  detractors   NPS answers scored 0 to 6

Score = w_reach * reach + w_frequency * frequency + w_recency * recency, where
  reach     = accounts / the most accounts on any opportunity, averaged with arr / the most arr when ARR is used
  frequency = signals / the most signals on any opportunity
ARR is used only when every account named in the run has an ARR. Otherwise it is shown with its coverage and
left out of the score, so a partial ARR file cannot reorder the list.

Ties break on accounts, then signals, then id. Default weights: reach 0.5, frequency 0.3, recency 0.2.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import datetime
from collections import Counter

from signals import Refused

WEIGHTS = {"reach": 0.5, "frequency": 0.3, "recency": 0.2}
HALF_LIFE_DAYS = 30


def parse_weights(text: str | None) -> dict[str, float]:
    if not text:
        return dict(WEIGHTS)
    out: dict[str, float] = {}
    for part in text.split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        if key not in WEIGHTS:
            raise Refused(f"--weights takes reach, frequency and recency. Got {key!r}.")
        try:
            out[key] = float(value)
        except ValueError:
            raise Refused(f"--weights: {key} must be a number. Got {value!r}.") from None
    if set(out) != set(WEIGHTS) or any(v < 0 for v in out.values()) or abs(sum(out.values()) - 1) > 1e-9:
        raise Refused("--weights must give reach, frequency and recency, none negative, summing to 1, for example reach=0.5,frequency=0.3,recency=0.2.")
    return out


def figures(opp: dict, as_of: datetime.date, arr: dict[str, float], half_life: int = HALF_LIFE_DAYS) -> dict:
    sigs = opp["signals"]
    accounts = sorted({s["account"] for s in sigs if s["account"]})
    dated = [datetime.date.fromisoformat(s["created"]) for s in sigs if s["created"]]
    ages = [max(0, (as_of - d).days) for d in dated]
    known = [a for a in accounts if a in arr]
    last = max(dated) if dated else None
    return {
        "signals": len(sigs),
        "mentions": len(sigs) + sum(len(s.get("duplicates", [])) for s in sigs),
        "accounts": len(accounts),
        "account_ids": accounts,
        "no_account_signals": sum(1 for s in sigs if not s["account"]),
        "arr": round(sum(arr[a] for a in known), 2) if known else None,
        "arr_accounts": len(known),
        "first_seen": min(dated).isoformat() if dated else None,
        "last_seen": last.isoformat() if last else None,
        "days_since_last": (as_of - last).days if last else None,
        "undated_signals": len(sigs) - len(dated),
        "recency": round(sum(0.5 ** (a / half_life) for a in ages) / len(ages), 4) if ages else 0.0,
        "detractors": sum(1 for s in sigs if s["kind"] == "nps" and s["score"] is not None and s["score"] <= 6),
        "by_source": dict(sorted(Counter(s["source"] for s in sigs).items())),
    }


def rank(opps: list[dict], as_of: datetime.date, arr: dict[str, float], weights: dict[str, float] | None = None, half_life: int = HALF_LIFE_DAYS) -> dict:
    """Opportunities with `figures`, `score`, `components` and `rank`, best first, and the basis used."""
    w = weights or dict(WEIGHTS)
    for o in opps:
        o["figures"] = figures(o, as_of, arr, half_life)
    named = sorted({a for o in opps for a in o["figures"]["account_ids"]})
    with_arr = [a for a in named if a in arr]
    use_arr = bool(named) and len(with_arr) == len(named)
    top_accounts = max((o["figures"]["accounts"] for o in opps), default=0)
    top_signals = max((o["figures"]["signals"] for o in opps), default=0)
    top_arr = max((o["figures"]["arr"] or 0 for o in opps), default=0)
    for o in opps:
        f = o["figures"]
        reach = f["accounts"] / top_accounts if top_accounts else 0.0
        if use_arr and top_arr:
            reach = (reach + (f["arr"] or 0) / top_arr) / 2
        comp = {"reach": round(reach, 4), "frequency": round(f["signals"] / top_signals if top_signals else 0.0, 4), "recency": f["recency"]}
        o["components"] = comp
        o["score"] = round(sum(w[k] * comp[k] for k in w), 4)
    opps.sort(key=lambda o: (-o["score"], -o["figures"]["accounts"], -o["figures"]["signals"], o["id"]))
    for i, o in enumerate(opps, 1):
        o["rank"] = i
    return {
        "weights": w,
        "half_life_days": half_life,
        "arr_used": use_arr,
        "arr_coverage": {"accounts_named": len(named), "accounts_with_arr": len(with_arr)},
        "opportunities": opps,
    }
