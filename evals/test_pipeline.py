"""The full run on the Acme fixture (illustrative): read, redact, dedupe, cluster, rank, quote, render.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual((self.digest["customer_base"], top["account_share"]), (16, 37.5))
        self.assertIn("6 accounts (37.5% of the customer base)", self.md)

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

    def test_tracker_csv_has_figures_and_ids_not_text(self) -> None:
        rows = list(csv.DictReader(io.StringIO((self.run_dir / "opportunities.csv").read_text())))
        self.assertEqual(rows[0]["id"], "quote-line-items")
        self.assertEqual((rows[0]["accounts"], rows[0]["rank_range"], rows[0]["illustrative"]), ("6", "1", "yes"))
        self.assertIn("zendesk:4101", rows[0]["source_ids"])
        self.assertNotIn("line items for labour", (self.run_dir / "opportunities.csv").read_text())

    def test_praise_only_marked_and_last(self) -> None:
        last = self.digest["opportunities"][-1]
        self.assertTrue(last["figures"]["praise_only"])
        self.assertIn("(praise only)", self.md)

    def test_follow_up_accounts_by_arr(self) -> None:
        self.assertEqual(self.opps["quote-line-items"]["figures"]["accounts_by_arr"][:2], ["9010", "9003"])
        self.assertIn("Accounts to talk to next, highest ARR first: 9010, 9003", self.md)

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


class ExtraTermsAndInspect(unittest.TestCase):
    def test_redact_terms_file(self) -> None:
        terms = Path(tempfile.mkdtemp(prefix="csd-")) / "terms.txt"
        terms.write_text("# extra terms\nboiler swap\nradiator valves\n")
        run_dir, digest = build_fixture("--redact-terms", str(terms))
        try:
            text = (run_dir / "digest.json").read_text()
            self.assertNotIn("boiler swap", text)
            self.assertNotIn("radiator valves", text)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)
            shutil.rmtree(terms.parent, ignore_errors=True)

    def test_inspect_shows_shape_not_text(self) -> None:
        f = helpers.FIXTURE
        code, out, _ = run_cli(
            [
                "inspect",
                "--zendesk",
                str(f / "zendesk-page-1.json"),
                "--intercom",
                str(f / "intercom-conversations.json"),
                "--csv-file",
                str(f / "call-notes.csv"),
                "--theme-prefix",
                "theme:",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("5 records, 2026-10-02 to 2026-11-22", out)
        self.assertIn("pass as person=: contact", out)
        self.assertIn("--intercom-account-attribute): account_id", out)
        for planted in fixture_personal_strings():
            self.assertNotIn(planted, out)
        self.assertNotIn("line items", out)


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
