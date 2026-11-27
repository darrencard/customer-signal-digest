#!/usr/bin/env python3
"""Remove duplicate signals, keeping every duplicate's ID as evidence.

Two signals are duplicates when:
  1. they share an ID (the same ticket read from two export pages), or
  2. their normalised text is identical (a pasted escalation, a forwarded ticket), or
  3. they come from the same account within WINDOW_DAYS of each other, the shorter has at least MIN_WORDS
     distinct words, and at least NEAR of those words appear in the longer (overlap coefficient), for example
     the same complaint sent by ticket and then restated in chat.

The earliest signal (then the lowest ID) is kept. Its `duplicates` list holds the IDs merged into it,
so reach and frequency count the problem once while the evidence trail keeps every source.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import datetime
import re

NEAR = 0.8
WINDOW_DAYS = 7
MIN_WORDS = 6

_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def overlap(a: set[str], b: set[str]) -> float:
    """Share of the smaller set's words found in the larger. 0 when the smaller has fewer than MIN_WORDS."""
    small = min(len(a), len(b))
    return len(a & b) / small if small >= MIN_WORDS else 0.0


def _days_apart(a: str, b: str) -> int | None:
    if not a or not b:
        return None
    return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)


def _order(s: dict) -> tuple[str, str]:
    return (s["created"] or "9999-12-31", s["id"])


def dedupe(signals: list[dict], near: float = NEAR, window_days: int = WINDOW_DAYS) -> tuple[list[dict], int]:
    """Kept signals in date then ID order, each with a sorted `duplicates` list, and how many signals were merged away."""
    kept: list[dict] = []
    by_id: dict[str, dict] = {}
    by_text: dict[str, dict] = {}
    merged = 0
    for s in sorted(signals, key=_order):
        s = {**s, "duplicates": list(s.get("duplicates", []))}
        norm = " ".join(_WORD.findall(s["text"].lower()))
        target = by_id.get(s["id"]) or by_text.get(norm)
        if target is None and s["account"]:
            mine = words(s["text"])
            for k in kept:
                apart = _days_apart(k["created"], s["created"])
                if k["account"] == s["account"] and apart is not None and apart <= window_days and overlap(words(k["text"]), mine) >= near:
                    target = k
                    break
        if target is not None:
            if s["id"] != target["id"] and s["id"] not in target["duplicates"]:
                target["duplicates"].append(s["id"])
            merged += 1
            continue
        kept.append(s)
        by_id[s["id"]] = s
        by_text.setdefault(norm, s)
    for k in kept:
        k["duplicates"].sort()
    return kept, merged
