#!/usr/bin/env python3
"""Check the words Claude writes for each opportunity (notes.json) before the digest renders.

notes.json:
  {"notes": {"<opportunity id>": {"title": "...", "summary": "..."}}}

Errors (any one blocks the render):
  unknown-opportunity   a note names an opportunity the digest does not have
  figure-not-computed   a number in the note is not one of that opportunity's computed figures
  overclaim             a phrase claims more than signal counts can show (all customers, will reduce churn, ...)
  quote-not-in-evidence text in quotation marks is not word for word in that opportunity's redacted evidence
  personal-data         the note holds an email, phone, card number, known name or another pattern redaction removes
  too-long              a title over 80 characters or a summary over 400
  title-is-a-solution   a title that starts with a build verb (Add, Build, Integrate ...): name the customer's problem

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import re

import redact

OVERCLAIM = (
    "all customers",
    "all of our customers",
    "every customer",
    "all accounts",
    "every account",
    "all users",
    "every user",
    "everyone",
    "no one",
    "nobody",
    "most customers",
    "majority of customers",
    "most accounts",
    "guaranteed",
    "proven",
    "will reduce churn",
    "will increase",
    "will drive",
    "is causing churn",
    "caused churn",
    "causes churn",
    "statistically significant",
)
SOLUTION_VERBS = ("add", "build", "create", "implement", "integrate", "launch", "ship", "make", "enable", "support", "introduce", "develop", "offer")
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
_QUOTED = re.compile(r"[\"“]([^\"”]{4,})[\"”]")


def _allowed_numbers(opp: dict) -> set[float]:
    f = opp["figures"]
    vals = [f["signals"], f["mentions"], f["accounts"], f["detractors"], f["days_since_last"], f["arr"], opp["rank"], f["no_account_signals"]]
    vals += [f["last_30_days"], f["prior_30_days"], f["passives"], f["promoters"], 30, *opp["rank_range"]]
    vals += list(f["by_source"].values())
    out = {float(v) for v in vals if v is not None}
    if f.get("account_share") is not None:
        out.add(float(f["account_share"]))
        out.add(float(round(f["account_share"])))
    if f["arr"] is not None:
        out |= {round(f["arr"] / 1000), round(f["arr"] / 1000, 1), round(f["arr"] / 1_000_000, 1), round(f["arr"] / 1_000_000, 2)}
    return out


def f_share(opp: dict) -> float | None:
    return opp["figures"].get("account_share")


def _numbers(text: str) -> list[tuple[str, float]]:
    out = []
    for m in _NUMBER.finditer(text):
        raw = m.group(0)
        out.append((raw, float(raw.rstrip("%").replace(",", ""))))
    return out


def check(notes: dict, digest: dict, salt: str, fingerprints: list[str]) -> list[dict]:
    """Every problem with the notes, as {"rule", "opportunity", "field", "detail"}. Empty means the notes may render."""
    opps = {o["id"]: o for o in digest["opportunities"]}
    errors: list[dict] = []

    def err(rule: str, oid: str, field: str, detail: str) -> None:
        errors.append({"rule": rule, "opportunity": oid, "field": field, "detail": detail})

    entries = notes.get("notes") if isinstance(notes, dict) else None
    if not isinstance(entries, dict):
        return [{"rule": "shape", "opportunity": "", "field": "", "detail": 'notes.json needs {"notes": {"<id>": {"title", "summary"}}}.'}]
    for oid, note in sorted(entries.items()):
        if oid not in opps:
            err("unknown-opportunity", oid, "", f"no opportunity {oid!r} in this digest")
            continue
        if not isinstance(note, dict):
            err("shape", oid, "", "each note is an object with title and summary")
            continue
        opp = opps[oid]
        allowed = _allowed_numbers(opp)
        evidence = [s["text"] for s in opp["signals"]]
        first = (str(note.get("title") or "").split() or [""])[0].lower().strip(",.:")
        if first in SOLUTION_VERBS:
            err("title-is-a-solution", oid, "title", f'starts with "{first}"; name the customer\'s problem, not a fix')
        for field, limit in (("title", 80), ("summary", 400)):
            text = str(note.get(field) or "")
            if len(text) > limit:
                err("too-long", oid, field, f"{len(text)} characters; the limit is {limit}")
            for raw, value in _numbers(text):
                pct_ok = raw.endswith("%") and f_share(opp) is not None and value in (f_share(opp), round(f_share(opp)))
                if (raw.endswith("%") and not pct_ok) or (not raw.endswith("%") and value not in allowed):
                    err("figure-not-computed", oid, field, f"{raw} is not a figure computed for this opportunity")
            low = text.lower()
            for phrase in OVERCLAIM:
                if re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", low):
                    err("overclaim", oid, field, f'"{phrase}": signal counts cannot show this')
            for q in _QUOTED.findall(text):
                if not any(q.strip() in e for e in evidence):
                    err("quote-not-in-evidence", oid, field, f'"{q.strip()}" is not word for word in its evidence')
            found = redact.leaks(text) + redact.fingerprint_hits(text, salt, fingerprints)
            for leak in sorted(set(found)):
                err("personal-data", oid, field, f"looks personal: {redact.mask(leak)}")
    return errors
