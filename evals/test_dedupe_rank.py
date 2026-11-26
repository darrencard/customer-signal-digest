"""Dedupe, clustering and ranking: duplicates count once and keep their IDs, and the order is computed, never chosen.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import datetime
import unittest

from helpers import cluster, dedupe, rank, signals

Refused = signals.Refused


def sig(sid: str, text: str, account: str = "a1", created: str = "2026-11-20", kind: str = "ticket", score: int | None = None, theme: str = "") -> dict:
    return {"id": sid, "source": sid.split(":")[0], "kind": kind, "created": created, "account": account, "text": text, "theme": theme, "score": score}


AS_OF = datetime.date(2026, 11, 26)


class Dedupe(unittest.TestCase):
    def test_same_id_counts_once(self) -> None:
        kept, merged = dedupe.dedupe([sig("z:1", "quote missing items"), sig("z:1", "quote missing items")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(merged, 1)
        self.assertEqual(kept[0]["duplicates"], [])

    def test_identical_text_across_accounts_merges(self) -> None:
        kept, _ = dedupe.dedupe([sig("z:1", "The chaser is wrong!", "a1"), sig("i:9", "the chaser is   wrong", "a2", "2026-11-21")])
        self.assertEqual([k["id"] for k in kept], ["z:1"])
        self.assertEqual(kept[0]["duplicates"], ["i:9"])

    def test_restated_complaint_same_account_within_window_merges(self) -> None:
        long = "Quote draft left off the materials. The assistant drafted a quote for a boiler swap and left off copper pipe and fittings."
        short = "The quote draft left off the materials for the boiler swap"
        kept, _ = dedupe.dedupe([sig("z:1", long, "a1", "2026-11-20"), sig("i:2", short, "a1", "2026-11-24")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["duplicates"], ["i:2"])

    def test_same_words_other_account_or_outside_window_kept(self) -> None:
        a = "The quote draft left off the materials for the boiler swap"
        kept, _ = dedupe.dedupe([sig("z:1", a, "a1", "2026-11-01"), sig("i:2", a + " again", "a1", "2026-11-20"), sig("i:3", a + " too", "a2", "2026-11-02")])
        self.assertEqual(len(kept), 3)


class Cluster(unittest.TestCase):
    THEMES = [
        {"id": "quotes", "name": "Quote drafts miss items", "keywords": ["line items", "quote draft"]},
        {"id": "chasers", "name": "Chasers after payment", "keywords": ["already paid", "chaser"]},
    ]

    def test_tag_then_map_then_similarity(self) -> None:
        sigs = [
            sig("z:1", "anything at all", theme="chasers"),
            sig("z:2", "the quote draft lost its line items"),
            sig("z:3", "please add dark mode to the dashboard"),
            sig("z:4", "dark mode for the dashboard please"),
            sig("z:5", "billing page is slow"),
        ]
        groups = {g["id"]: g for g in cluster.cluster(sigs, self.THEMES)}
        self.assertEqual([s["id"] for s in groups["chasers"]["signals"]], ["z:1"])
        self.assertEqual(groups["chasers"]["how"], "source tag")
        self.assertEqual(groups["quotes"]["signals"][0]["grouped_by"], "keywords")
        self.assertEqual(groups["unnamed-1"]["how"], "similarity")
        self.assertEqual([s["id"] for s in groups["quotes"]["signals"]], ["z:2"])
        self.assertEqual([s["id"] for s in groups["unnamed-1"]["signals"]], ["z:3", "z:4"])
        self.assertEqual([s["id"] for s in groups["unnamed-2"]["signals"]], ["z:5"])

    def test_keyword_tie_goes_to_first_listed(self) -> None:
        groups = cluster.cluster([sig("z:1", "quote draft and chaser")], self.THEMES)
        self.assertEqual([g["id"] for g in groups], ["quotes"])

    def test_whole_words_only(self) -> None:
        groups = cluster.cluster([sig("z:1", "the chasers were lovely")], self.THEMES)
        self.assertTrue(groups[0]["id"].startswith("unnamed-"))


class Rank(unittest.TestCase):
    def opps(self) -> list[dict]:
        return [
            {"id": "wide", "name": "Wide", "signals": [sig(f"z:{i}", "x", f"a{i}", "2026-11-01") for i in range(4)]},
            {"id": "loud", "name": "Loud", "signals": [sig(f"y:{i}", "x", "a9", "2026-11-25") for i in range(6)]},
        ]

    def test_reach_outweighs_frequency_by_default(self) -> None:
        out = rank.rank(self.opps(), AS_OF, {})
        self.assertEqual([o["id"] for o in out["opportunities"]], ["wide", "loud"])
        self.assertEqual(out["opportunities"][0]["figures"]["accounts"], 4)
        self.assertFalse(out["arr_used"])

    def test_weights_change_the_order(self) -> None:
        out = rank.rank(self.opps(), AS_OF, {}, rank.parse_weights("reach=0.1,frequency=0.5,recency=0.4"))
        self.assertEqual(out["opportunities"][0]["id"], "loud")

    def test_arr_used_only_with_full_coverage(self) -> None:
        full = {f"a{i}": 1000.0 for i in range(4)} | {"a9": 100000.0}
        out = rank.rank(self.opps(), AS_OF, full)
        self.assertTrue(out["arr_used"])
        self.assertEqual(out["opportunities"][0]["id"], "loud")
        partial = {"a9": 100000.0}
        out = rank.rank(self.opps(), AS_OF, partial)
        self.assertFalse(out["arr_used"])
        self.assertEqual(out["arr_coverage"], {"accounts_named": 5, "accounts_with_arr": 1})
        self.assertEqual([o["id"] for o in out["opportunities"]], ["wide", "loud"])

    def test_recency_and_figures(self) -> None:
        o = {"id": "o", "name": "o", "signals": [sig("z:1", "x", "a1", "2026-11-26"), sig("z:2", "x", "", "2026-10-27", kind="nps", score=3)]}
        o["signals"][0]["duplicates"] = ["i:5"]
        o["signals"][1]["duplicates"] = []
        f = rank.figures(o, AS_OF, {})
        self.assertEqual(f["recency"], 0.75)
        self.assertEqual((f["signals"], f["mentions"], f["accounts"], f["no_account_signals"], f["detractors"]), (2, 3, 1, 1, 1))
        self.assertEqual(f["days_since_last"], 0)

    def test_bad_weights_refused(self) -> None:
        for bad in ("reach=1", "reach=0.5,frequency=0.5,recency=0.5", "reach=0.5,frequency=0.6,recency=-0.1", "speed=1"):
            with self.subTest(bad=bad), self.assertRaises(Refused):
                rank.parse_weights(bad)


if __name__ == "__main__":
    unittest.main()
