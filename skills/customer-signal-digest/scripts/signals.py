#!/usr/bin/env python3
"""Read customer signals into one shape: support tickets, call notes, NPS and survey answers.

Readers:
  zendesk   tickets, search or search export pages as Zendesk returns them ({"tickets": [...]} or {"results": [...]}).
            A page fetched with include=users carries {"users": [...]}; their names and emails are passed to redaction.
  intercom  conversation search pages ({"conversations": [...]}). The opening message is source.body (HTML).
  csv       any export with a header row: call notes, NPS, survey answers. Columns are named with flags; nothing is guessed.

Every signal becomes:
  {"id": "zendesk:4101", "source": "zendesk", "kind": "ticket", "created": "2026-11-02", "account": "org-17",
   "text": "...", "theme": "", "score": None}

plus a set of known personal strings (names, emails) found in the record's metadata, kept apart from the signal
so redaction can remove them from the text.

This module reads files. It makes no network calls. Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import csv
import datetime
import html
import io
import json
import re
from pathlib import Path
from typing import Any

Json = dict[str, Any]
KINDS = ("ticket", "conversation", "call", "nps", "survey")


class Refused(Exception):
    """An input the scripts will not read as it stands. The message says what to change."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Refused(f"cannot read {path} ({e}). Save the system's response as it stands, as UTF-8 JSON.") from None


def read_csv(path: Path) -> list[Json]:
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise Refused(f"cannot read {path} ({e}).") from None
    return list(csv.DictReader(io.StringIO(text)))


def day(value: Any) -> str:
    """A date as YYYY-MM-DD from ISO text or epoch seconds or milliseconds. Empty when it cannot be read."""
    if value is None or value == "":
        return ""
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, (int, float)):
        seconds = value / 1000 if abs(value) > 10**11 else value
        return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc).date().isoformat()
    text = str(value).strip()
    try:
        return datetime.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return ""


_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<\s*(br|/p|/div|/li)\s*/?>", re.I)


def plain(text: Any) -> str:
    """HTML to plain text, line breaks kept, whitespace tidied."""
    s = _BREAK.sub("\n", str(text or ""))
    s = html.unescape(_TAG.sub("", s))
    lines = [" ".join(line.split()) for line in s.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _signal(source: str, kind: str, sid: Any, created: Any, account: Any, text: str, theme: str = "", score: Any = None) -> Json:
    return {
        "id": f"{source}:{sid}",
        "source": source,
        "kind": kind,
        "created": day(created),
        "account": "" if account in (None, "") else str(account),
        "text": text,
        "theme": theme,
        "score": score,
    }


def _items(data: Any, *keys: str) -> list[Json] | None:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    for key in keys:
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return [x for x in data[key] if isinstance(x, dict)]
    return None


def _theme(tags: list[str], prefix: str | None) -> str:
    if not prefix:
        return ""
    return next((t[len(prefix) :].strip() for t in tags if t.lower().startswith(prefix.lower()) and t[len(prefix) :].strip()), "")


def from_zendesk(paths: list[str], theme_prefix: str | None = None) -> tuple[list[Json], set[str]]:
    signals: list[Json] = []
    known: set[str] = set()
    for p in paths:
        data = load_json(Path(p))
        tickets = _items(data, "tickets", "results")
        if tickets is None:
            raise Refused(f"{p} holds no list under tickets or results, as Zendesk returns them.")
        for u in _items(data, "users") or []:
            known.update(str(u.get(k)) for k in ("name", "email") if u.get(k))
        for t in tickets:
            if t.get("result_type", "ticket") != "ticket":
                continue
            text = plain("\n".join(x for x in (str(t.get("subject") or ""), str(t.get("description") or "")) if x))
            tags = [str(x) for x in t.get("tags") or []]
            signals.append(_signal("zendesk", "ticket", t.get("id"), t.get("created_at"), t.get("organization_id"), text, _theme(tags, theme_prefix)))
    return signals, known


def from_intercom(paths: list[str], theme_prefix: str | None = None, account_attribute: str | None = None) -> tuple[list[Json], set[str]]:
    signals: list[Json] = []
    known: set[str] = set()
    for p in paths:
        conversations = _items(load_json(Path(p)), "conversations")
        if conversations is None:
            raise Refused(f"{p} holds no list under conversations, as Intercom returns them.")
        for c in conversations:
            src = c.get("source") or {}
            author = src.get("author") or {}
            known.update(str(author.get(k)) for k in ("name", "email") if author.get(k))
            text = plain("\n".join(x for x in (str(src.get("subject") or ""), str(src.get("body") or "")) if x))
            tags = [t.get("name", "") for t in ((c.get("tags") or {}).get("tags") or []) if isinstance(t, dict)]
            account = (c.get("custom_attributes") or {}).get(account_attribute) if account_attribute else ""
            signals.append(_signal("intercom", "conversation", c.get("id"), c.get("created_at"), account, text, _theme(tags, theme_prefix)))
    return signals, known


def from_csv(
    path: str,
    source: str,
    kind: str,
    id_col: str = "id",
    text_col: str = "text",
    date_col: str = "created_at",
    account_col: str | None = "account",
    theme_col: str | None = None,
    score_col: str | None = None,
    person_cols: tuple[str, ...] = (),
) -> tuple[list[Json], set[str], int]:
    """Rows with no text (an NPS score with no comment) are counted and left out: there is nothing to quote."""
    if kind not in KINDS:
        raise Refused(f"kind must be one of {', '.join(KINDS)}. Got {kind!r}.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", source):
        raise Refused(f"source must be a short lower-case name such as calls or nps. Got {source!r}.")
    rows = read_csv(Path(path))
    if rows:
        missing = [c for c in (id_col, text_col, date_col, account_col, theme_col, score_col, *person_cols) if c and c not in rows[0]]
        if missing:
            raise Refused(f"{path} has no column named {', '.join(missing)}. Its columns are: {', '.join(rows[0])}.")
    signals: list[Json] = []
    known: set[str] = set()
    no_text = 0
    for r in rows:
        known.update(str(r[c]).strip() for c in person_cols if str(r.get(c) or "").strip())
        text = " ".join(str(r.get(text_col) or "").split())
        if not text:
            no_text += 1
            continue
        score: Any = None
        if score_col and str(r.get(score_col) or "").strip():
            try:
                score = int(str(r[score_col]).strip())
            except ValueError:
                raise Refused(f"{path}: {score_col} must be a whole number. Row {r.get(id_col)!r} has {r[score_col]!r}.") from None
        theme = str(r.get(theme_col) or "").strip() if theme_col else ""
        signals.append(_signal(source, kind, r.get(id_col), r.get(date_col), r.get(account_col) if account_col else "", text, theme, score))
    return signals, known, no_text


def read_accounts(path: str, account_col: str = "account", arr_col: str = "arr") -> dict[str, float]:
    """Account to ARR. A blank ARR is left out, never read as zero."""
    out: dict[str, float] = {}
    for r in read_csv(Path(path)):
        acct, raw = str(r.get(account_col) or "").strip(), str(r.get(arr_col) or "").replace(",", "").strip()
        if not acct or not raw:
            continue
        try:
            out[acct] = float(raw)
        except ValueError:
            raise Refused(f"{path}: {arr_col} for {acct!r} is {raw!r}, not a number.") from None
    return out


def count_accounts(path: str, account_col: str = "account") -> int:
    """Distinct named accounts in an accounts file: the customer base for a share of accounts."""
    return len({str(r.get(account_col) or "").strip() for r in read_csv(Path(path))} - {""})
