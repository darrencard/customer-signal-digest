"""The Landing Loop record: one JSON file per bet, landing/<bet-slug>.json, shared by the loop's skills and the Leader Report.

customer-signal-digest is step 04 Learn. It reads the brief and the `landed` key did-it-land wrote, and writes only
its own key, `signals`. Every other key is kept exactly as it was found. It reads no key later in the record order
(portfolio, decisions, spec, release, cost, evals, landed, signals, postmortem, board_qa).

It prints the bet's status from `landed.status` and never computes one. Its own check has two words of its own:
"problem still raised" when a theme the person tied to the bet's problem has a signal in the last 30 days, and
"problem not raised" when none has. Every figure carries value, unit, source, window (from, to) and as_of.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "landing-loop/1"
KEY = "signals"
READS = ("landed",)
ORDER = ("portfolio", "decisions", "spec", "release", "cost", "evals", "landed", "signals", "postmortem", "board_qa")
CHECK_WORDS = ("problem still raised", "problem not raised")
MAX_RECORD_BYTES = 2_000_000
RECENT_DAYS = 30


class RecordError(ValueError):
    """A loop record that cannot be used. Nothing is written when this is raised."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_for(folder: Path, bet: str) -> Path:
    return folder / "landing" / f"{bet}.json"


def load(folder: Path, bet: str) -> dict[str, Any] | None:
    """The record as it stands, or None when there is none yet. Refused if it is not a landing-loop/1 record for this bet."""
    p = path_for(folder, bet)
    if not p.exists():
        return None
    if p.stat().st_size > MAX_RECORD_BYTES:
        raise RecordError(f"{p} is over {MAX_RECORD_BYTES:,} bytes, so it is not a loop record.")
    try:
        record = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RecordError(f"{p} is not valid JSON ({e}). Fix it or move it; it is never overwritten.") from None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise RecordError(f"{p} is not a {SCHEMA} record. It is left as it is.")
    if record.get("bet") != bet:
        raise RecordError(f"{p} is the record for {record.get('bet')!r}, not {bet!r}. It is left as it is.")
    return record


def brief_path(folder: Path, record: dict[str, Any] | None, given: str | None) -> Path:
    """The brief: the one the record names (its path is relative to the working folder), or --brief for a new record.
    A brief edited after the record opened is refused: every step must read the same brief."""
    if record and isinstance(record.get("brief"), dict) and record["brief"].get("path"):
        p = folder / record["brief"]["path"]
        if not p.exists():
            raise RecordError(f"the record names the brief {record['brief']['path']}, which is not in {folder}.")
        if given and Path(given).resolve() != p.resolve():
            raise RecordError(f"--brief {given} is not the brief the record names ({record['brief']['path']}). Every step reads one brief.")
        if record["brief"].get("sha256") and sha256(p) != record["brief"]["sha256"]:
            raise RecordError(f"{p} changed after the record opened (its sha256 no longer matches). Every step must read the same brief; nothing was written.")
        return p
    if not given:
        raise RecordError("there is no record yet, so pass --brief with the bet's landing brief.")
    return Path(given)


def figure(value: Any, unit: str, source: str, window: tuple[str | None, str | None], as_of: str) -> dict[str, Any]:
    """One figure in the loop's shape. No figure without a source."""
    if not source:
        raise RecordError("a figure has no source. Every figure in the loop record needs one.")
    return {"value": value, "unit": unit, "source": source, "window": {"from": window[0], "to": window[1]}, "as_of": as_of}


def printed_status(record: dict[str, Any] | None) -> dict[str, Any]:
    """The bet's status as did-it-land wrote it, copied, never computed. None when did-it-land has not run."""
    landed = (record or {}).get("landed")
    if not isinstance(landed, dict) or landed.get("status") not in ("landed", "watch", "stalled"):
        return {"status": None, "printed_from": "landed.status", "note": "not read yet: run did-it-land"}
    out: dict[str, Any] = {"status": landed["status"], "printed_from": "landed.status", "computed_by": landed.get("computed_by", "did-it-land")}
    cur = (landed.get("figures") or {}).get("current")
    if isinstance(cur, dict) and "value" in cur and cur.get("source"):
        out["metric"] = landed.get("metric", "")
        out["current"] = cur
    return out


def _sources(digest: dict[str, Any]) -> str:
    return "; ".join(f"{i['system']}: {', '.join(i['files'])}" for i in digest["inputs"])


LIVE = "Live: API pages saved as returned"
FALLBACK = "CSV fallback"


def signals_key(digest: dict[str, Any], record: dict[str, Any] | None, brief: Any, brief_file: Path, bet: str) -> dict[str, Any]:
    """The `signals` key, from the digest's computed figures. Every number here was counted in rank.py or below."""
    as_of = digest["as_of"]
    win = (digest["window"]["from"], digest["window"]["to"])
    day = datetime.date.fromisoformat(as_of)
    recent = ((day - datetime.timedelta(days=RECENT_DAYS - 1)).isoformat(), min(as_of, win[1]))
    prior = ((day - datetime.timedelta(days=2 * RECENT_DAYS - 1)).isoformat(), (day - datetime.timedelta(days=RECENT_DAYS)).isoformat())
    tool = f"customer-signal-digest {digest['version']}"
    ill = " (illustrative)" if digest["illustrative"] else ""
    src = _sources(digest) + ill

    def fig(value: Any, unit: str, how: str, window: tuple[str | None, str | None] = win) -> dict[str, Any]:
        return figure(value, unit, f"{tool}: {how}; {src}", window, as_of)

    opps = digest["opportunities"]
    mine = [o for o in opps if o.get("bet") == bet]
    problem = [o for o in mine if o.get("side") == "problem"]
    praise = [o for o in mine if o.get("side") == "praise"]

    def total(group: list[dict[str, Any]], name: str) -> int:
        return sum(o["figures"][name] for o in group)

    def accounts(group: list[dict[str, Any]]) -> list[str]:
        return sorted({a for o in group for a in o["figures"]["account_ids"]})

    kept = digest["counts"]["kept"]
    on_bet = total(mine, "signals")
    figures = {
        "signals": fig(kept, "signals", "signals in the window after duplicates were merged"),
        "accounts": fig(len({a for o in opps for a in o["figures"]["account_ids"]}), "accounts", "distinct accounts named on those signals"),
        "on_bet_signals": fig(on_bet, "signals", f"signals in themes tied to {bet}"),
        "on_bet_share": fig(round(100 * on_bet / kept, 1) if kept else 0.0, "%", f"signals in themes tied to {bet} / all signals"),
        "problem_signals": fig(total(problem, "signals"), "signals", "signals in themes on the problem side"),
        "problem_accounts": fig(len(accounts(problem)), "accounts", "distinct accounts on the problem side"),
        "problem_last_30_days": fig(total(problem, "last_30_days"), "signals", "problem-side signals in the last 30 days", recent),
        "problem_prior_30_days": fig(total(problem, "prior_30_days"), "signals", "problem-side signals in the 30 days before", prior),
        "praise_signals": fig(total(praise, "signals"), "signals", "signals in themes on the praise side"),
        "praise_accounts": fig(len(accounts(praise)), "accounts", "distinct accounts on the praise side"),
    }
    if not problem:
        check, reason = None, f'not checked: no theme is tied to {bet}\'s problem. Add "bet" and "side" to themes.json.'
    elif figures["problem_last_30_days"]["value"] > 0:
        check = CHECK_WORDS[0]
        reason = (
            f"{figures['problem_signals']['value']} signals from {figures['problem_accounts']['value']} accounts say the problem is still there, "
            f"{figures['problem_last_30_days']['value']} of them in the last 30 days."
        )
    else:
        check = CHECK_WORDS[1]
        reason = f"No signal on the problem side in the last 30 days ({figures['problem_signals']['value']} in the whole window)."

    themes = []
    n = len(opps)
    for o in opps:
        f = o["figures"]
        themes.append(
            {
                "id": o["id"],
                "name": o["name"],
                "side": o.get("side") if o.get("bet") == bet else "other",
                "rank": fig(o["rank"], f"rank of {n} themes", "reach, frequency and recency, ranked in code"),
                "figures": {
                    "signals": fig(f["signals"], "signals", "deduplicated signals in this theme"),
                    "accounts": fig(f["accounts"], "accounts", "distinct accounts in this theme"),
                    "last_30_days": fig(f["last_30_days"], "signals", "signals in the last 30 days", recent),
                    "prior_30_days": fig(f["prior_30_days"], "signals", "signals in the 30 days before", prior),
                    **({"arr": fig(f["arr"], "ARR", f"summed ARR of {f['arr_accounts']} accounts, from the accounts file")} if f["arr"] is not None else {}),
                },
                "talk_to": f["accounts_by_arr"],
                "quotes": [{"text": q["text"], "ids": q["ids"], "created": q["created"], "illustrative": digest["illustrative"]} for q in o.get("quotes", [])],
            }
        )

    arr = digest.get("arr_by_account") or {}
    talk = sorted(accounts(problem), key=lambda a: (-arr.get(a, 0.0), a))
    if check == CHECK_WORDS[0]:
        next_step = f"Talk to the {len(talk)} accounts on the problem side, highest ARR first ({', '.join(talk)}), before deciding whether to scale the bet."
    elif check == CHECK_WORDS[1]:
        next_step = "Keep the digest running; decide on scale from the metric and the brief's bar."
    else:
        next_step = f"Tie the themes about {bet} to its problem or to praise in themes.json, then build again."
    return {
        "tool": tool,
        "as_of": as_of,
        "window": {"from": win[0], "to": win[1]},
        "illustrative": digest["illustrative"],
        "check": check,
        "check_reason": reason,
        "bet_status": printed_status(record),
        "brief": {
            "path": brief_file.name,
            "problem": brief.problem,
            "metric": brief.metric,
            "bar": brief.bar_text,
            "better": "higher" if brief.higher_is_better else "lower",
            "by": brief.by,
        },
        "figures": figures,
        "themes": themes,
        "inputs": [
            {
                "system": i["system"],
                "files": i["files"],
                "how": FALLBACK if i["system"].startswith("CSV") else LIVE,
                "signals": fig(i["signals"], "signals", f"read from {i['system']}"),
            }
            for i in digest["inputs"]
        ],
        "left_out": {k: fig(v, "rows" if "rows" in k else "signals", f"left out: {k}") for k, v in digest["counts"]["left_out"].items() if v},
        "duplicates_merged": fig(digest["counts"]["duplicates_merged"], "signals", "signals merged into another as the same complaint"),
        "redacted_spans": fig(sum(digest["counts"]["redacted_spans"].values()), "spans", "personal-data spans replaced before grouping"),
        "next_step": next_step,
        "decides": brief.decides,
    }


def write(folder: Path, bet: str, brief_file: Path, record: dict[str, Any] | None, key: dict[str, Any]) -> Path:
    """Write the `signals` key. A new record gets schema, bet and brief; an existing one keeps every other key unchanged."""
    p = path_for(folder, bet)
    if record is None:
        rel = Path(os.path.relpath(brief_file.resolve(), folder.resolve())).as_posix()
        record = {"schema": SCHEMA, "bet": bet, "brief": {"path": rel, "sha256": sha256(brief_file)}}
    record = dict(record)
    record[KEY] = key
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p
