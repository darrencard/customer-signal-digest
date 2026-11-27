"""Shared helpers for the evals: the scripts on the path, and one run of the full pipeline on the Acme fixture.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "customer-signal-digest" / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "acme"
sys.path.insert(0, str(SCRIPTS))

import cluster  # noqa: E402  (the scripts, found through the path above)
import dedupe  # noqa: E402
import digest  # noqa: E402
import rank  # noqa: E402
import redact  # noqa: E402
import signals  # noqa: E402
import validate  # noqa: E402

__all__ = ["cluster", "dedupe", "digest", "rank", "redact", "signals", "validate"]

AS_OF = "2026-11-26"


def build_args(run: Path, *extra: str) -> list[str]:
    f = FIXTURE
    return [
        "build",
        "--run",
        str(run),
        "--as-of",
        AS_OF,
        "--zendesk",
        str(f / "zendesk-page-1.json"),
        str(f / "zendesk-page-2.json"),
        "--intercom",
        str(f / "intercom-conversations.json"),
        "--intercom-account-attribute",
        "account_id",
        "--theme-prefix",
        "theme:",
        "--csv",
        f"source=calls,kind=call,file={f / 'call-notes.csv'},id=call_id,date=date,text=notes,person=contact",
        "--csv",
        f"source=nps,kind=nps,file={f / 'nps.csv'},id=response_id,date=submitted_at,text=comment,score=score",
        "--accounts",
        str(f / "accounts.csv"),
        "--themes",
        str(f / "themes.json"),
        "--illustrative",
        *extra,
    ]


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = digest.main(argv)
    return code, out.getvalue(), err.getvalue()


def build_fixture(*extra: str) -> tuple[Path, dict]:
    run = Path(tempfile.mkdtemp(prefix="csd-"))
    code, _, err = run_cli(build_args(run, *extra))
    if code != 0:
        raise AssertionError(f"build failed: {err}")
    return run, json.loads((run / "digest.json").read_text())


def fixture_personal_strings() -> list[str]:
    """Every invented name, email, phone, card and address planted in the fixture, as written there."""
    return [
        "Priya Raman",
        "Priya",
        "Raman",
        "priya.raman@harbourplumbing.example",
        "604-555-0142",
        "Tom Okafor",
        "Okafor",
        "4111 1111 1111 1111",
        "Grace Lindqvist",
        "Grace",
        "Ahmed",
        "Siddiqui",
        "Dev Patel",
        "dev.patel@pateldrainage.example",
        "14 Elm Street",
        "V5K 0A1",
        "Sam Whitfield",
        "Whitfield",
        "+44 20 7946 0958",
        "Nadia Brennan",
        "Nadia",
        "Ivan Petrov",
        "token=abc123",
        "portal.example",
    ]
