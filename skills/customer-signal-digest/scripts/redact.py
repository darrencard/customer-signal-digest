#!/usr/bin/env python3
"""Remove personal data from signal text before anything is clustered, quoted or written.

What it removes, each replaced with a bracketed label:
  [EMAIL]    email addresses
  [URL]      web addresses (they can carry tokens and names in the path or query)
  [CARD]     13 to 19 digit card numbers that pass the Luhn check
  [IBAN]     bank account numbers in IBAN form
  [PHONE]    phone numbers: 9 to 15 digits with the usual separators, or a leading +
  [IP]       IPv4 addresses
  [POSTCODE] UK and Canadian postcodes
  [ADDRESS]  a house number followed by a street name and a street word (Street, Road, Ave and so on)
  [NAME]     names known from the source (requester, author, contact columns), names after "my name is",
             "this is", "speaking with", a title (Mr, Ms, Dr), and the name under a sign-off (Thanks, Cheers, Regards)

The rules are patterns, so they can miss. `leaks()` re-checks redacted text with the same patterns and the
known names, and the digest refuses to quote any text where it finds one.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"')]+", re.I)
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")
CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
PHONE = re.compile(r"(?<![\w-])(?:\+\d[\d ().-]{7,18}\d|\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}|0\d{2,4}[ ]\d{3,4}[ ]\d{3,4})(?![\w-])")
IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
POSTCODE = re.compile(r"\b(?:[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}|[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d)\b")
ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Way|Close|Crescent|Court|Ct|Boulevard|Blvd|Place|Pl)\b\.?"
)
_NAME = r"[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)?"
INTRO = re.compile(r"\b(?i:my name is|my name's|this is|speaking with|spoke with|spoke to|talked to|call with)\s+(" + _NAME + r")")
TITLE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Mx|Dr)\.?\s+(" + _NAME + r")")
_SIGNOFF_WORDS = r"(?i:thanks|thank you|cheers|regards|kind regards|best|best regards|many thanks|ta)"
SIGNOFF = re.compile(r"(?m)^" + _SIGNOFF_WORDS + r"[,!.]?[ \t]*(?:\n|[ \t]+-?[ \t]*)(" + _NAME + r")[ \t]*$")

# Words that follow "this is" or a sign-off but are not names. Kept short on purpose; a miss here over-redacts, which is safe.
NOT_NAMES = {"The", "This", "That", "It", "Our", "We", "Urgent", "Still", "Again", "Not", "Very", "Really", "Happening", "Broken", "A", "An"}

LABELS = ("EMAIL", "URL", "CARD", "IBAN", "PHONE", "IP", "POSTCODE", "ADDRESS", "NAME")


def luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _cards(text: str, counts: Counter[str]) -> str:
    def swap(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn(digits):
            counts["CARD"] += 1
            return "[CARD]"
        return m.group(0)

    return CARD_CANDIDATE.sub(swap, text)


def _sub(pattern: re.Pattern[str], label: str, text: str, counts: Counter[str]) -> str:
    out, n = pattern.subn(f"[{label}]", text)
    counts[label] += n
    return out


def _names_in_group(pattern: re.Pattern[str], text: str, counts: Counter[str]) -> str:
    def swap(m: re.Match[str]) -> str:
        name = m.group(1)
        first = name.split()[0]
        if first in NOT_NAMES:
            return m.group(0)
        counts["NAME"] += 1
        start, end = m.span(1)
        return m.group(0)[: start - m.start()] + "[NAME]" + m.group(0)[end - m.start() :]

    return pattern.sub(swap, text)


def _known_pattern(known: Iterable[str]) -> re.Pattern[str] | None:
    """Known strings, longest first, plus each part of a multi-word name of 3 or more letters (a first name alone still identifies)."""
    parts = _parts(known)
    if not parts:
        return None
    alts = "|".join(re.escape(p) for p in sorted(parts, key=lambda s: (-len(s), s)))
    return re.compile(r"(?<![\w@])(?:" + alts + r")(?![\w@])")


def redact(text: str, known: Iterable[str] = ()) -> tuple[str, Counter[str]]:
    """The text with personal data replaced, and how many spans of each kind were replaced."""
    counts: Counter[str] = Counter()
    s = _sub(EMAIL, "EMAIL", text, counts)
    s = _sub(URL, "URL", s, counts)
    s = _sub(IBAN, "IBAN", s, counts)
    s = _cards(s, counts)
    s = _sub(IPV4, "IP", s, counts)
    s = _sub(PHONE, "PHONE", s, counts)
    s = _sub(POSTCODE, "POSTCODE", s, counts)
    s = _sub(ADDRESS, "ADDRESS", s, counts)
    pattern = _known_pattern(known)
    if pattern:
        s = _sub(pattern, "NAME", s, counts)
    for p in (INTRO, TITLE, SIGNOFF):
        s = _names_in_group(p, s, counts)
    return s, +counts


def leaks(text: str, known: Iterable[str] = ()) -> list[str]:
    """What still looks personal in text that should already be redacted. Empty means clean."""
    found = [m.group(0) for p in (EMAIL, URL, IBAN, IPV4, PHONE, POSTCODE, ADDRESS) for m in p.finditer(text)]
    found += [m.group(0) for m in CARD_CANDIDATE.finditer(text) if luhn(re.sub(r"\D", "", m.group(0))) and 13 <= len(re.sub(r"\D", "", m.group(0))) <= 19]
    pattern = _known_pattern(known)
    if pattern:
        found += [m.group(0) for m in pattern.finditer(text)]
    for p in (INTRO, TITLE, SIGNOFF):
        found += [m.group(1) for m in p.finditer(text) if m.group(1).split()[0] not in NOT_NAMES]
    return sorted(set(found))


def _parts(known: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for k in known:
        k = " ".join(str(k).split())
        if len(k) >= 3:
            out.add(k)
            if "@" not in k:
                out.update(w for w in k.split() if len(w) >= 3 and w[0].isupper())
    return out


def fingerprints(known: Iterable[str], salt: str) -> list[str]:
    """Salted hashes of known names and emails, so a run can check later text for them without storing them."""
    return sorted(hashlib.sha256((salt + p).encode()).hexdigest() for p in _parts(known))


def fingerprint_hits(text: str, salt: str, prints: Iterable[str]) -> list[str]:
    """Words and runs of up to 3 words in text whose salted hash is a known name or email. Case counts, as in redact()."""
    wanted = set(prints)
    if not wanted:
        return []
    tokens = re.findall(r"[\w.+'@-]+", text)
    hits = []
    for n in (1, 2, 3):
        for i in range(len(tokens) - n + 1):
            chunk = " ".join(tokens[i : i + n]).strip(".-'")
            if hashlib.sha256((salt + chunk).encode()).hexdigest() in wanted:
                hits.append(chunk)
    return hits


def mask(value: str) -> str:
    """A leak shown back to the user without repeating it: first character, then its length."""
    return f"{value[:1]}{'*' * max(0, len(value) - 1)} ({len(value)} characters)"


def redact_signals(signals: list[dict], known: Iterable[str] = ()) -> Counter[str]:
    """Redact every signal's text in place. Returns the total spans replaced, by kind."""
    known = list(known)
    total: Counter[str] = Counter()
    for s in signals:
        s["text"], counts = redact(s["text"], known)
        total.update(counts)
    return total
