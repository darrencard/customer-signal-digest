"""The notes Claude writes are checked before the digest renders: no invented figures, overclaims, false quotes or personal data.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import json
import shutil
import unittest

from helpers import build_fixture, run_cli


class Notes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run_dir, cls.digest = build_fixture()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.run_dir, ignore_errors=True)

    def render(self, notes: dict) -> tuple[int, str]:
        path = self.run_dir / "notes.json"
        path.write_text(json.dumps({"notes": notes}))
        code, _, err = run_cli(["render", "--run", str(self.run_dir), "--notes", str(path)])
        return code, err

    def test_supported_note_renders(self) -> None:
        code, err = self.render(
            {
                "quote-line-items": {
                    "title": "Quote drafts drop line items",
                    "summary": 'Raised by 6 accounts in 7 signals; one says the draft is "missing line items for labour".',
                }
            }
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Quote drafts drop line items", (self.run_dir / "digest.md").read_text())

    def test_each_rule_blocks(self) -> None:
        cases = {
            "figure-not-computed": {"title": "Seen by 40 accounts"},
            "overclaim": {"summary": "Every customer hits this and fixing it will reduce churn."},
            "quote-not-in-evidence": {"summary": 'A customer said "the AI is useless".'},
            "personal-data": {"summary": "Priya Raman raised it first; reach her at priya@example.com."},
            "unknown-opportunity": None,
        }
        for rule, note in cases.items():
            with self.subTest(rule=rule):
                notes = {"no-such-id": {"title": "x"}} if note is None else {"quote-line-items": note}
                code, err = self.render(notes)
                self.assertEqual(code, 1)
                self.assertIn(f"error {rule}", err)

    def test_percentages_are_not_computed(self) -> None:
        code, err = self.render({"quote-line-items": {"summary": "Up 50% this month."}})
        self.assertEqual(code, 1)
        self.assertIn("figure-not-computed", err)

    def test_leak_report_does_not_repeat_the_name(self) -> None:
        _, err = self.render({"quote-line-items": {"summary": "Ask Grace about it."}})
        self.assertIn("personal-data", err)
        self.assertNotIn("Grace", err)


if __name__ == "__main__":
    unittest.main()
