#!/usr/bin/env python3
"""Group deduplicated signals into opportunities, in code, in three passes.

1. Theme tag. A signal whose source tagged a theme joins the opportunity with that id or name in the theme map,
   or an opportunity named after the tag.
2. Theme map. The map (themes.json) lists opportunities with keywords. A signal joins the opportunity whose
   keywords it matches most often, whole words only; a tie goes to the one listed first. Claude may draft
   the map from a read of the signals; the user confirms it; code applies it.
3. Similarity. What is left is grouped by single-link word overlap (Jaccard at least SIMILAR on content words).
   These groups are named "unnamed-N" with their top terms, for the user to name or fold into the map.

themes.json:
  {"opportunities": [{"id": "quote-line-items", "name": "Quote drafts miss line items",
                      "keywords": ["line item", "missing items", "quote draft"],
                      "bet": "quote-drafting", "side": "problem"}]}

"bet" and "side" are optional and go together. They tie a theme to a shipped bet: side "problem" when its
signals say the brief's problem is still there, "praise" when they say it is gone. The person confirms both;
code never guesses which themes are about the bet.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from signals import Refused, load_json

SIMILAR = 0.3
SIDES = ("problem", "praise")

STOP = frozenset(
    re.findall(
        r"\S+",
        """a about after again all also am an and any are as at be been before being but by can cannot could did do does doing
    don't for from get got had has have having he her here him his how i i'm if in into is it it's its just me more most my
    no not now of off on once only or other our out over please same she so some still than that the their them then there
    these they this those to too up us very was we were what when where which while who why will with would you your hi hello
    thanks thank team""",
    )
)
_WORD = re.compile(r"[a-z][a-z']+")
_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-") or "theme"


def stem(w: str) -> str:
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return w


def terms(text: str) -> set[str]:
    """Content words, lower case, lightly stemmed. Redaction labels such as [NAME] are not terms."""
    return {stem(w) for w in _WORD.findall(re.sub(r"\[[A-Z]+\]", " ", text).lower()) if w not in STOP and len(w) > 2}


def load_themes(path: str | None) -> list[dict]:
    if not path:
        return []
    data = load_json(Path(path))
    opps = data.get("opportunities") if isinstance(data, dict) else None
    if not isinstance(opps, list):
        raise Refused(f'{path} needs {{"opportunities": [{{"id", "name", "keywords"}}]}}.')
    seen: set[str] = set()
    out = []
    for o in opps:
        if not isinstance(o, dict) or not o.get("id") or not o.get("name"):
            raise Refused(f"{path}: every opportunity needs an id and a name. Got {o!r}.")
        oid = slug(str(o["id"]))
        if oid in seen:
            raise Refused(f"{path}: the id {oid!r} appears twice.")
        seen.add(oid)
        kws = [str(k).lower().strip() for k in o.get("keywords") or [] if str(k).strip()]
        bet, side = str(o.get("bet") or "").strip(), str(o.get("side") or "").strip()
        if bool(bet) != bool(side) or (side and side not in SIDES):
            raise Refused(f'{path}: {oid} ties itself to a bet with both "bet" (the bet\'s slug) and "side" ({" or ".join(SIDES)}), or neither. Got bet={bet!r}, side={side!r}.')
        out.append({"id": oid, "name": str(o["name"]), "keywords": kws, "bet": bet, "side": side})
    return out


def _hits(text: str, keywords: list[str]) -> int:
    low = text.lower()
    return sum(len(re.findall(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", low)) for k in keywords)


def cluster(signals: list[dict], themes: list[dict], similar: float = SIMILAR) -> list[dict]:
    """Opportunities as {"id", "name", "how", "signals": [...]}, in theme-map order, then tag order, then unnamed.
    Each signal carries `grouped_by` (source tag, keywords or similarity); `how` lists the ways used in the group."""
    by_key = {t["id"]: t for t in themes} | {t["name"].lower(): t for t in themes}
    groups: dict[str, dict] = {t["id"]: {"id": t["id"], "name": t["name"], "how": "", "bet": t.get("bet", ""), "side": t.get("side", ""), "signals": []} for t in themes}
    rest: list[dict] = []
    for s in signals:
        tag = (s.get("theme") or "").strip()
        if tag:
            t = by_key.get(slug(tag)) or by_key.get(tag.lower())
            gid = t["id"] if t else slug(tag)
            groups.setdefault(gid, {"id": gid, "name": tag, "how": "", "bet": "", "side": "", "signals": []})["signals"].append({**s, "grouped_by": "source tag"})
            continue
        scores = [(_hits(s["text"], t["keywords"]), -i, t["id"]) for i, t in enumerate(themes)]
        best = max(scores, default=(0, 0, ""))
        if best[0] > 0:
            groups[best[2]]["signals"].append({**s, "grouped_by": "keywords"})
        else:
            rest.append(s)
    clusters: list[list[dict]] = []
    for s in rest:
        mine = terms(s["text"])
        best_i, best_sim = -1, 0.0
        for i, members in enumerate(clusters):
            sim = max(_jaccard(mine, terms(m["text"])) for m in members)
            if sim > best_sim:
                best_i, best_sim = i, sim
        if best_i >= 0 and best_sim >= similar:
            clusters[best_i].append({**s, "grouped_by": "similarity"})
        else:
            clusters.append([{**s, "grouped_by": "similarity"}])
    for n, members in enumerate(clusters, 1):
        counts = Counter(t for m in members for t in terms(m["text"]))
        shown = _surface(members)
        top = [shown.get(t, t) for t, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        gid = f"unnamed-{n}"
        groups[gid] = {"id": gid, "name": f"Unnamed: {', '.join(top) or 'no content words'}", "how": "", "bet": "", "side": "", "signals": members}
    out = [g for g in groups.values() if g["signals"]]
    for g in out:
        g["how"] = " and ".join(sorted({s["grouped_by"] for s in g["signals"]}))
    return out


def _surface(members: list[dict]) -> dict[str, str]:
    """Each stem's first word as written, so a name reads "invoicing", not "invoic"."""
    out: dict[str, str] = {}
    for m in members:
        for w in _WORD.findall(re.sub(r"\[[A-Z]+\]", " ", m["text"]).lower()):
            out.setdefault(stem(w), w)
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0
