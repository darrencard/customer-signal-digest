#!/usr/bin/env python3
"""Regenerate the committed Acme sample: customer-signal-digest.html, its Markdown twin, and the signals key of landing/quote-drafting.json.

Inputs, all illustrative (Acme is an invented company): the canonical quote-drafting brief in briefs/ (copied from
the landing-loop repo, unchanged), upstream/quote-drafting.json (the landing-loop record filtered to the keys this
skill reads: schema, bet, brief and did-it-land's landed), and the customer feedback in feedback/ (written by
evals/make_sample.py). Feedback window 2026-09-07 to 2026-11-24, as of 2026-11-26. The same inputs give the same bytes.

Usage, from the repo root:
  python3 examples/acme/sample.py [--into DIR]

--into writes the outputs somewhere else (the test uses it); paths inside the outputs stay the same.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036  (the floor, checked before anything is read or written)
    sys.exit("customer-signal-digest needs Python 3.11 or later; try python3.12")

ROOT = Path(__file__).resolve().parents[2]
HERE = Path("examples/acme")
FEED = HERE / "feedback"
sys.path.insert(0, str(ROOT / "skills" / "customer-signal-digest" / "scripts"))

import digest  # noqa: E402

BET = "quote-drafting"


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--into", help="output folder (default examples/acme)")
    args = p.parse_args(argv)
    os.chdir(ROOT)  # sources written into the record name files relative to the repo root
    into = Path(args.into).resolve() if args.into else ROOT / HERE
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as work_dir:
        # Build in a scratch folder and move the outputs into place only on success, so a failed run never leaves
        # the committed record stripped back to its upstream keys.
        work = Path(work_dir)
        (work / "landing").mkdir()
        (work / "briefs").mkdir()
        # Start from the record as did-it-land left it: this skill reads landed and writes only signals.
        shutil.copy(HERE / "upstream" / f"{BET}.json", work / "landing" / f"{BET}.json")
        shutil.copy(HERE / "briefs" / f"{BET}.md", work / "briefs" / f"{BET}.md")
        rc = digest.main(
            [
                "build", "--run", tmp, "--as-of", "2026-11-26", "--since", "2026-09-07", "--until", "2026-11-24", "--illustrative",
                "--zendesk", str(FEED / "zendesk-page-1.json"), str(FEED / "zendesk-page-2.json"),
                "--intercom", str(FEED / "intercom-conversations.json"), "--intercom-account-attribute", "account_id", "--theme-prefix", "theme:",
                "--csv", f"source=calls,kind=call,file={FEED / 'calls.csv'},id=call_id,date=date,text=notes,person=contact",
                "--csv", f"source=nps,kind=nps,file={FEED / 'nps.csv'},id=response_id,date=submitted_at,text=comment,score=score",
                "--accounts", str(FEED / "accounts.csv"), "--themes", str(FEED / "themes.json"),
                "--loop", str(work), "--bet", BET, "--html", str(work / "customer-signal-digest.html"),
            ]
        )  # fmt: skip
        if rc:
            raise SystemExit(rc)
        (into / "landing").mkdir(parents=True, exist_ok=True)
        (into / "briefs").mkdir(parents=True, exist_ok=True)
        if into != (ROOT / HERE).resolve():
            shutil.copy(HERE / "briefs" / f"{BET}.md", into / "briefs" / f"{BET}.md")
        for name in ("customer-signal-digest.html", "customer-signal-digest.md", f"landing/{BET}.json"):
            staged = into / f"{name}.tmp"
            shutil.copy(work / name, staged)
            staged.replace(into / name)
    print(f"sample: wrote customer-signal-digest.html, customer-signal-digest.md and landing/{BET}.json to {into}")


if __name__ == "__main__":
    main()
