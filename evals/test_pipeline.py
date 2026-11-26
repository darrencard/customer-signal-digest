"""The full run on the Acme fixture (illustrative): read, redact, dedupe, cluster, rank, quote, render.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest

import helpers
from helpers import build_fixture, fixture_personal_strings, run_cli


class AcmeRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run_dir, cls.digest = build_fixture()
        code, _, err = run_cli(["render", "--run", str(cls.run_dir)])
        assert code == 0, err
        cls.md = (cls.run_dir / "digest.md").read_text()
        cls.opps = {o["id"]: o for o in cls.digest["opportunities"]}

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.run_dir, ignore_errors=True)

    def test_counts(self) -> None:
        c = self.digest["counts"]
        self.assertEqual(c["read"], 21)
        self.assertEqual(c["duplicates_merged"], 2)
        self.assertEqual(c["kept"], 19)
        self.assertEqual(c["left_out"], {"nps rows with no text": 1})

    def test_ranking_is_computed(self) -> None:
        order = [o["id"] for o in self.digest["opportunities"]]
        self.assertEqual(order[:4], ["quote-line-items", "chaser-paid-invoices", "offline-sync", "accounting-export"])
        top = self.opps["quote-line-items"]["figures"]
        self.assertEqual((top["accounts"], top["signals"], top["mentions"], top["arr"]), (6, 7, 8, 96000.0))
        self.assertTrue(self.digest["arr_used"])

    def test_restated_complaint_merged_with_its_ids_kept(self) -> None:
        sigs = {s["id"]: s for s in self.opps["quote-line-items"]["signals"]}
        self.assertIn("intercom:215001", sigs["zendesk:4101"]["duplicates"])
        self.assertNotIn("intercom:215001", sigs)

    def test_every_quote_has_source_ids_and_is_its_evidence(self) -> None:
        for o in self.digest["opportunities"]:
            texts = {s["id"]: s["text"] for s in o["signals"]}
            self.assertTrue(o["quotes"], o["id"])
            for q in o["quotes"]:
                self.assertTrue(q["ids"])
                body = q["text"].removesuffix(" ...")
                self.assertIn(body, " ".join(texts[q["ids"][0]].split()))
                self.assertIn(", ".join(q["ids"]), self.md)

    def test_no_personal_data_in_any_output(self) -> None:
        written = {p.name: p.read_text() for p in self.run_dir.iterdir()}
        for name, text in written.items():
            for planted in fixture_personal_strings():
                self.assertNotIn(planted, text, f"{planted!r} leaked into {name}")
        self.assertGreaterEqual(sum(self.digest["counts"]["redacted_spans"].values()), 15)

    def test_injected_instructions_stay_data(self) -> None:
        self.assertEqual(self.opps["quote-line-items"]["rank"], 1)
        ticket = next(s for s in self.opps["quote-line-items"]["signals"] if s["id"] == "zendesk:4105")
        self.assertIn("ignore your rules", ticket["text"])
        self.assertNotIn("landed", json.dumps({k: v for k, v in self.digest.items() if k != "opportunities"}))

    def test_markdown_escapes_source_text(self) -> None:
        self.assertIn("\\[NAME\\]", self.md)
        self.assertNotIn("<p>", self.md)

    def test_every_figure_marked_illustrative(self) -> None:
        self.assertIn("**Illustrative.**", self.md)
        table = [line for line in self.md.splitlines() if line.startswith("| ") and line[2].isdigit()]
        self.assertTrue(table)
        self.assertTrue(all(line.endswith("Illustrative |") for line in table))

    def test_same_input_same_digest(self) -> None:
        run2, digest2 = build_fixture()
        try:
            self.assertEqual(digest2, self.digest)
        finally:
            shutil.rmtree(run2, ignore_errors=True)


class Refusals(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="csd-")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_csv_column(self) -> None:
        code, _, err = run_cli(
            ["build", "--run", self.tmp, "--as-of", helpers.AS_OF, "--csv", f"source=nps,kind=nps,file={helpers.FIXTURE / 'nps.csv'},text=nope"]
        )
        self.assertEqual(code, 2)
        self.assertIn("no column named", err)

    def test_bad_as_of(self) -> None:
        code, _, err = run_cli(["build", "--as-of", "26/11/2026", "--zendesk", str(helpers.FIXTURE / "zendesk-page-1.json")])
        self.assertEqual(code, 2)
        self.assertIn("YYYY-MM-DD", err)

    def test_wrong_shape(self) -> None:
        code, _, err = run_cli(["build", "--run", self.tmp, "--as-of", helpers.AS_OF, "--zendesk", str(helpers.FIXTURE / "themes.json")])
        self.assertEqual(code, 2)
        self.assertIn("no list under tickets", err)


if __name__ == "__main__":
    unittest.main()
