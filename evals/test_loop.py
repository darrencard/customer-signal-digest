"""Hold customer-signal-digest 0.3's Landing Loop promises.

Usage:
  python3 -m unittest discover -s evals -v
  python3 -m pytest evals

Groups:
  Vendored    the vendored Leader Report files are byte for byte what VENDORED.json names; the brief parser is 2d13573543c74ebe.
  Record      writes only the signals key; landed and every other key stay byte-identical; reads nothing later in the order.
  Figures     every figure in the key carries value, unit, source, window (from, to) and as_of; no bare numbers.
  StatusWords landed, watch and stalled appear only as printed from landed.status; the check uses its own words.
  Sample      the README command reproduces the committed page, Markdown twin and record byte for byte.
  Brief       an incomplete brief or a brief edited after the record opened is refused, and nothing is written.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "customer-signal-digest"
SCRIPTS = SKILL / "scripts"
ACME = ROOT / "examples" / "acme"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "vendor"))

import digest  # noqa: E402
import loop  # noqa: E402
import render_html  # noqa: E402
import signals  # noqa: E402
import svgkit  # noqa: E402

STATUS = re.compile(r"\b(landed|watch|stalled)\b", re.I)


def run_sample(into: Path) -> None:
    with redirect_stdout(io.StringIO()):
        subprocess.run([sys.executable, str(ACME / "sample.py"), "--into", str(into)], check=True, capture_output=True)  # noqa: S603


def walk(obj, path=""):
    """Every (path, value) leaf, and every dict, in a JSON tree."""
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


class Vendored(unittest.TestCase):
    def test_hashes_match_the_pin(self) -> None:
        pins = json.loads((SKILL / "VENDORED.json").read_text())
        self.assertEqual(pins["commit"], "366da9bfede540ec19e9164ad5ad17ce28c1d06b")
        for rel, meta in pins["files"].items():
            with self.subTest(rel):
                self.assertEqual(hashlib.sha256((SKILL / rel).read_bytes()).hexdigest(), meta["sha256"])
        self.assertTrue(pins["files"]["scripts/vendor/landing_brief.py"]["sha256"].startswith("2d13573543c74ebe"))

    def test_status_rule_is_never_called(self) -> None:
        for p in SCRIPTS.glob("*.py"):
            with self.subTest(p.name):
                self.assertNotIn("status_for", p.read_text())

    def test_zendesk_pages_read_as_the_leader_report_reads_them(self) -> None:
        import convert

        page = ACME / "feedback" / "zendesk-page-1.json"
        got, _ = signals.from_zendesk([str(page)], "theme:")
        theirs = convert.pages([str(page)], "test", "tickets", "results")
        self.assertEqual([s["id"] for s in got], [f"zendesk:{t['id']}" for t in theirs])
        self.assertEqual([s["created"] for s in got], [convert.day(t["created_at"]).isoformat() for t in theirs])


class Record(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        run_sample(cls.out)
        cls.text = (cls.out / "landing" / "quote-drafting.json").read_text()
        cls.record = json.loads(cls.text)
        cls.upstream_text = (ACME / "upstream" / "quote-drafting.json").read_text()
        cls.upstream = json.loads(cls.upstream_text)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_writes_only_its_own_key(self) -> None:
        self.assertEqual(set(self.record) - set(self.upstream), {"signals"})
        for k in self.upstream:
            self.assertEqual(self.record[k], self.upstream[k], k)

    def test_read_keys_are_byte_identical(self) -> None:
        for k in ("brief", "landed"):
            a = json.dumps(self.upstream[k], indent=2, ensure_ascii=False)
            b = json.dumps(self.record[k], indent=2, ensure_ascii=False)
            self.assertEqual(a, b, k)
            self.assertIn(a.replace("\n", "\n  "), self.text, k)

    def test_upstream_is_the_landing_loop_record_filtered(self) -> None:
        self.assertEqual(list(self.upstream), ["schema", "bet", "brief", "landed"])
        self.assertEqual(self.upstream["brief"]["sha256"], "decbe39590cc57b3d47125722a8d43e445d33c8f2f525c00277b94b7937dc95f")
        self.assertEqual(hashlib.sha256((ACME / "briefs" / "quote-drafting.md").read_bytes()).hexdigest(), self.upstream["brief"]["sha256"])

    def test_reads_only_earlier_keys(self) -> None:
        self.assertEqual(loop.READS, ("landed",))
        order = loop.ORDER
        for k in loop.READS:
            self.assertLess(order.index(k), order.index(loop.KEY))

    def test_other_keys_survive_untouched(self) -> None:
        """A record with keys from every other skill keeps each of them, later keys included, exactly."""
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            run_sample(into)
            p = into / "landing" / "quote-drafting.json"
            rec = json.loads(p.read_text())
            rec["postmortem"] = {"note": "written later", "n": {"value": 1, "unit": "x", "source": "s", "window": {"from": None, "to": None}, "as_of": "2026-11-27"}}
            rec["cost"] = {"kept": True}
            p.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
            before = {k: json.dumps(v) for k, v in rec.items() if k != "signals"}
            self.assertEqual(run_sample_keep(into), 0)
            after = json.loads(p.read_text())
            for k, v in before.items():
                self.assertEqual(json.dumps(after[k]), v, k)

    def test_record_key_order_is_kept(self) -> None:
        self.assertEqual(list(self.record), ["schema", "bet", "brief", "landed", "signals"])

    def test_check_and_figures(self) -> None:
        s = self.record["signals"]
        self.assertEqual(s["check"], "problem still raised")
        self.assertEqual(s["bet_status"]["status"], self.upstream["landed"]["status"])
        self.assertEqual(s["window"], {"from": "2026-09-07", "to": "2026-11-24"})
        self.assertEqual(s["as_of"], "2026-11-26")
        f = s["figures"]
        self.assertEqual((f["problem_signals"]["value"], f["problem_accounts"]["value"], f["problem_last_30_days"]["value"]), (7, 7, 5))
        self.assertEqual(f["on_bet_signals"]["value"], f["problem_signals"]["value"] + f["praise_signals"]["value"])
        self.assertTrue(all(q["illustrative"] for t in s["themes"] for q in t["quotes"]))


def run_sample_keep(into: Path) -> int:
    """Run the build on the sample's inputs into an existing record, without resetting it from upstream. Returns the exit code."""
    feed = ACME / "feedback"
    with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return digest.main(
            [
                "build", "--run", tmp, "--as-of", "2026-11-26", "--since", "2026-09-07", "--until", "2026-11-24", "--illustrative",
                "--zendesk", str(feed / "zendesk-page-1.json"), str(feed / "zendesk-page-2.json"),
                "--intercom", str(feed / "intercom-conversations.json"), "--intercom-account-attribute", "account_id", "--theme-prefix", "theme:",
                "--csv", f"source=nps,kind=nps,file={feed / 'nps.csv'},id=response_id,date=submitted_at,text=comment,score=score",
                "--themes", str(feed / "themes.json"), "--loop", str(into), "--bet", "quote-drafting",
            ]
        )  # fmt: skip


def build_argv(into: Path, *extra: str) -> list[str]:
    feed = ACME / "feedback"
    tmp = tempfile.mkdtemp()
    return [
        "build", "--run", tmp, "--as-of", "2026-11-26", "--themes", str(feed / "themes.json"),
        "--csv", f"source=nps,kind=nps,file={feed / 'nps.csv'},id=response_id,date=submitted_at,text=comment,score=score",
        "--loop", str(into), "--bet", "quote-drafting", *extra,
    ]  # fmt: skip


class Figures(unittest.TestCase):
    def test_every_figure_carries_source_and_window(self) -> None:
        key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]
        figs = [(p, d) for p, d in walk(key) if isinstance(d, dict) and "value" in d]
        self.assertGreater(len(figs), 20)
        for p, d in figs:
            with self.subTest(p):
                self.assertEqual(set(d), {"value", "unit", "source", "window", "as_of"})
                self.assertTrue(d["source"] and d["unit"] and d["as_of"])
                self.assertEqual(set(d["window"]), {"from", "to"})
                self.assertTrue(d["window"]["from"] and d["window"]["to"])

    def test_no_bare_numbers_outside_figures(self) -> None:
        key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]
        inside = {p for p, d in walk(key) if isinstance(d, dict) and "value" in d}
        for p, v in walk(key):
            if isinstance(v, int | float) and not isinstance(v, bool):
                with self.subTest(p):
                    self.assertTrue(any(p == f"{q}.value" for q in inside), p)

    def test_page_figures_come_from_the_key(self) -> None:
        """Every bold number in the page's figures column is a figure value in the key."""
        key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]
        page = (ACME / "customer-signal-digest.html").read_text()
        figs = page.split('<dl class="figs">', 1)[1].split("</dl>", 1)[0]
        facts = re.findall(r"<b>([^<]+)</b>", figs)
        self.assertEqual(len(facts), 4)
        values = {str(d["value"]) for _, d in walk(key) if isinstance(d, dict) and "value" in d} | {
            f"{d['value']:g}%" for _, d in walk(key) if isinstance(d, dict) and d.get("unit") == "%"
        }
        values.add(key["brief"]["bar"])  # the target, as the landing brief states it
        for f in facts:
            with self.subTest(f):
                self.assertIn(re.sub(r" signals?$", "", f).replace(",", ""), values)


class StatusWords(unittest.TestCase):
    def test_status_words_only_from_landed_status(self) -> None:
        key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]
        hits = [p for p, v in walk(key) if isinstance(v, str) and STATUS.search(v)]
        # bet_status.value is the copy; printed_from and the copied figure's source name where it came from.
        self.assertEqual([p for p in hits if p not in ("bet_status.status", "bet_status.printed_from")], [])

    def test_page_prints_status_only_as_copied(self) -> None:
        """The status word prints in its mark, the heading and the engineers' note, and is always the copied one."""
        page = (ACME / "customer-signal-digest.html").read_text()
        body = re.sub(r"<style>.*?</style>", "", page, flags=re.S)
        self.assertEqual(body.count('<span class="st landed">landed</span>'), 1)
        self.assertIn("<h1>Quote drafting landed, but 7 customer accounts still raise the problem.</h1>", body)
        words = STATUS.findall(re.sub(r"<[^>]+>", " ", body.replace("landed.status", "")))
        self.assertEqual(set(words), {"landed"})

    def test_markdown_prints_status_only_as_copied(self) -> None:
        md = (ACME / "customer-signal-digest.md").read_text().replace("landed.status", "")
        self.assertEqual(set(STATUS.findall(md)), {"landed"})
        self.assertTrue(md.startswith("# Quote drafting landed, but 7 customer accounts still raise the problem.\n"))

    def test_check_words_are_its_own(self) -> None:
        for w in loop.CHECK_WORDS:
            self.assertIsNone(STATUS.search(w))

    def test_no_status_colour_on_the_check(self) -> None:
        page = (ACME / "customer-signal-digest.html").read_text()
        for m in re.finditer(r'<span class="chk">[^<]*</span>', page):
            self.assertNotIn("st ", m.group(0))

    def test_status_follows_the_record(self) -> None:
        """Change landed.status upstream and the page prints the new word; the digest computes none."""
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            (into / "briefs").mkdir()
            shutil.copy(ACME / "briefs" / "quote-drafting.md", into / "briefs")
            (into / "landing").mkdir()
            rec = json.loads((ACME / "upstream" / "quote-drafting.json").read_text())
            rec["landed"]["status"] = "stalled"
            (into / "landing" / "quote-drafting.json").write_text(json.dumps(rec))
            self.assertEqual(run_sample_keep(into), 0)
            self.assertEqual(json.loads((into / "landing" / "quote-drafting.json").read_text())["signals"]["bet_status"]["status"], "stalled")

    def test_no_landed_key_prints_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            (into / "briefs").mkdir()
            shutil.copy(ACME / "briefs" / "quote-drafting.md", into / "briefs")
            (into / "landing").mkdir()
            rec = json.loads((ACME / "upstream" / "quote-drafting.json").read_text())
            del rec["landed"]
            (into / "landing" / "quote-drafting.json").write_text(json.dumps(rec))
            self.assertEqual(run_sample_keep(into), 0)
            bs = json.loads((into / "landing" / "quote-drafting.json").read_text())["signals"]["bet_status"]
            self.assertIsNone(bs["status"])
            self.assertIn("run did-it-land", bs["note"])


class Floor(unittest.TestCase):
    """Python 3.11 is the floor; a failed run never strips the record."""

    def test_every_entry_script_stops_on_an_old_python_with_a_plain_message(self) -> None:
        for path in (SCRIPTS / "digest.py", ACME / "sample.py", ROOT / "evals" / "make_sample.py"):
            code = f"import runpy, sys; sys.version_info = (3, 9, 6); runpy.run_path({str(path)!r}, run_name='__main__')"
            done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
            self.assertEqual(done.returncode, 1, path.name)
            self.assertIn("needs Python 3.11 or later", done.stderr, path.name)
            self.assertIn("try python3.12", done.stderr, path.name)

    def test_a_render_failure_leaves_the_record_as_it_was(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            run_sample(into)
            p = into / "landing" / "quote-drafting.json"
            before = p.read_bytes()
            argv = [*build_argv(into), "--html", str(into / "page.html")]
            with mock.patch.object(render_html, "page", side_effect=TypeError("boom")), self.assertRaises(TypeError), redirect_stdout(io.StringIO()):
                digest.main(argv)
            self.assertEqual(p.read_bytes(), before)
            self.assertIn(b'"signals"', before)
            self.assertFalse((into / "page.html").exists())

    def test_a_failed_sample_run_leaves_the_committed_record_as_it_was(self) -> None:
        sys.path.insert(0, str(ACME))
        import sample  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            run_sample(into)
            before = (into / "landing" / "quote-drafting.json").read_bytes()
            with mock.patch.object(render_html, "page", side_effect=TypeError("boom")), self.assertRaises(TypeError), redirect_stdout(io.StringIO()):
                sample.main(["--into", str(into)])
            self.assertEqual((into / "landing" / "quote-drafting.json").read_bytes(), before)


class Visual(unittest.TestCase):
    """The page in the Landing Loop's one visual family: svgkit pinned, the picture honest, the words plain."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.page = (ACME / "customer-signal-digest.html").read_text()
        cls.md = (ACME / "customer-signal-digest.md").read_text()
        cls.key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]

    def test_svgkit_matches_its_landing_loop_pin(self) -> None:
        pin = json.loads((SKILL / "VENDORED.json").read_text())["landing-loop"]
        self.assertEqual(pin["commit"], "78784efd2ecd5282f6ec264e545ce2075e459be2")
        self.assertEqual(set(pin["files"]), {"scripts/vendor/svgkit.py"})
        for rel, info in pin["files"].items():
            digest_ = hashlib.sha256((SKILL / rel).read_bytes()).hexdigest()
            self.assertEqual(digest_, info["sha256"], f"{rel} changed. Copy it again from landing-loop at the pinned commit and update VENDORED.json.")

    def test_the_visual_draws_only_figures_the_page_prints(self) -> None:
        self.assertEqual(svgkit.unprinted(self.page), [])
        frame = svgkit.frames_in(self.page)[0]
        self.assertIn('<span class="sc-l"><b>7 accounts</b> · 5 of 7 signals in 30 days</span>', frame)
        self.assertIn('<span class="sc-l"><b>5 accounts</b> · 2 of 5 signals in 30 days</span>', frame)
        f = self.key["figures"]
        # Each share bar draws the last 30 days of one side as a share of that side's signals.
        widths = re.findall(r'<rect class="a" x="0" y="0" width="([^"]+)"', frame)
        p = f["problem_last_30_days"]["value"] / f["problem_signals"]["value"] * 100
        self.assertEqual(widths, [svgkit.num(p) + "%", svgkit.num(2 / f["praise_signals"]["value"] * 100) + "%"])

    # The scorecard grammar (landing-loop tools/SCORECARD-ROLLOUT.md, svgkit 1.2.0)

    def css(self) -> str:
        return self.page.split("<style>", 1)[1].split("</style>", 1)[0]

    def test_one_frame_two_rows_and_the_check_word_on_the_problem_row(self) -> None:
        frames = svgkit.frames_in(self.page)
        self.assertEqual(len(frames), 1)
        self.assertEqual(re.findall(r'<span class="sc-n">([^<]+)</span>', frames[0]), ["Still feel the problem", "Problem gone"])
        rows = re.findall(r'<div class="sc-r">.*?</span></div>', frames[0])
        self.assertIn('<span class="sc-w ink">PROBLEM STILL RAISED</span>', rows[0])
        self.assertEqual(frames[0].count('class="sc-w'), 1)

    def test_no_text_inside_a_picture_and_no_scaled_picture(self) -> None:
        self.assertEqual(svgkit.svgs_with_text(self.page), [])
        self.assertEqual(svgkit.scaled_svgs_in(self.page), [])

    def test_the_figure_column_prints_in_one_case(self) -> None:
        self.assertIn(".scg .sc-l{text-transform:uppercase;letter-spacing:.06em}", self.css())

    def test_labels_render_12px_and_names_14px(self) -> None:
        css = self.css()
        self.assertEqual(set(svgkit.font_sizes(css)), {"var(--sc-m)", "var(--sc-n)"})
        self.assertIn("--sc-m:calc(12px / var(--sc-z))", css)
        self.assertIn("--sc-n:calc(14px / var(--sc-z))", css)
        self.assertIn(".scg{--sc-z:1;", css, "a sample page has no zoom")

    def test_no_box_inside_the_frame_and_no_overlap(self) -> None:
        self.assertEqual(svgkit.boxes_in_frames(self.page, self.css()), [])
        self.assertNotIn("position:absolute", svgkit.SCORECARD_CSS)
        self.assertNotIn('class="chip"', self.page.split("For your engineers", 1)[0])
        self.assertNotIn('class="panel"', self.page, "no card around the frame")

    def test_no_legacy_svgkit_primitive_draws_on_the_page(self) -> None:
        import warnings

        self.assertEqual(svgkit.legacy_in(self.page), [])
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            render_html.page(self.key, "quote-drafting")

    def test_no_status_colour_in_the_frame(self) -> None:
        frame = svgkit.frames_in(self.page)[0]
        self.assertNotIn('class="ac ', frame)
        self.assertNotIn('class="st ', frame)

    def test_green_and_red_only_beside_their_words(self) -> None:
        body = self.page.split("</style>", 1)[1]
        rest = re.sub(r'<span class="st (landed|stalled)">\1</span>', "", body)
        for word in ("landed", "stalled"):
            self.assertNotIn(f"var(--{word})", rest)
            self.assertNotIn(f"st {word}", rest)
        self.assertEqual(body.count('<span class="st landed">landed</span>'), 1)

    def test_each_visual_states_its_answer(self) -> None:
        labels = re.findall(r'role="img" aria-label="([^"]+)"', self.page)
        self.assertEqual(len(labels), 1)
        for label in labels:
            self.assertEqual(
                label,
                "7 signals from 7 accounts say customers still feel the problem, 5 in the last 30 days; "
                "5 signals from 5 accounts say it is gone, 2 in the last 30 days. Problem still raised.",
            )

    def test_public_copy_uses_plain_words(self) -> None:
        public = svgkit.page_text(self.page.split("For your engineers", 1)[0]).lower()
        md = self.md.split("## For your engineers", 1)[0].lower()
        for text in (public, md):
            for word in (" bet ", " bets ", " bar ", ".json", "landed.status", "signals key", "eval"):
                self.assertNotIn(word, text)
        self.assertIn("<b>landing brief</b>, a one-page plan (what good looks like, by when, at what cost)", self.page)
        self.assertIn("is a project you expect to move a number", self.page)
        for text in (public, md):
            for word in (r"\brecords?\b", r"\bbets?\b", r"\bthe bar\b", r"\bprds?\b", r"\barr\b", r"\btokens?\b", r"customer-signal-digest", r"did-it-land"):
                self.assertIsNone(re.search(word, text), word)

    def test_accounts_print_by_revenue_as_account_ids(self) -> None:
        talk = ", ".join(f"account {a}" for a in self.key["themes"][0]["talk_to"])
        self.assertIn("account 9010, account 9003", talk)
        for text in (self.page, self.md):
            self.assertIn(f"highest revenue first ({talk})", text)
            self.assertIn(f"Accounts to talk to, highest revenue first: {talk}", text)
        self.assertIn("highest ARR first (9010,", self.key["next_step"], "the project file keeps its own words")

    def test_no_text_is_smaller_than_11px(self) -> None:
        css = " ".join(re.findall(r"<style>(.*?)</style>", self.page, re.DOTALL)) + " " + " ".join(re.findall(r'style="([^"]*)"', self.page))
        sizes = re.findall(r"font-size\s*:\s*([\d.]+)px", css) + re.findall(r"font\s*:[^;{}]*?(?<![\w.-])([\d.]+)px", css)
        sizes += re.findall(r'font-size="([\d.]+)"', self.page)
        self.assertTrue(sizes)
        self.assertEqual([s for s in sizes if float(s) < 11], [])
        self.assertNotRegex(css, r"font-size\s*:\s*[\d.]+r?em")
        before, after = ".a{font:400 10px/16px var(--mono)}.b{font-size:10.5px}.c{font-size:13px}", ".a{font:400 11px/16px var(--mono)}.b{font-size:11px}.c{font-size:13px}"
        self.assertEqual(render_html.floor_fonts(before), after)

    def test_the_header_prints_the_plain_name_and_the_code_name_is_for_engineers(self) -> None:
        self.assertEqual(re.search(r'<span class="sk-meta"><span>(.*?)</span>', self.page).group(1), "Customer signals")
        self.assertTrue(self.md.split("\n")[2].startswith("Customer signals v0.3.3."))
        self.assertIn("Built by customer-signal-digest 0.3.3.", self.page.split("For your engineers", 1)[1])
        self.assertIn("Built by customer-signal-digest 0.3.3.", self.md.split("## For your engineers", 1)[1])

    def test_the_page_follows_the_sample_anatomy(self) -> None:
        body = self.page.split('<main class="solo">', 1)[1]
        order = ['class="sk-hdr"', "<h1>", 'class="marks"', '<div class="sc scg"', "What to do next", 'class="cols"', "For your engineers"]
        at = [body.index(x) for x in order]
        self.assertEqual(at, sorted(at))
        self.assertEqual(body.count("<h1>"), 1)
        self.assertIn("<details><summary>For your engineers</summary>", body)
        self.assertIn("<span>Customer signals</span><span>As of 2026-11-26</span><span>v0.3.3</span>", body)
        self.assertNotIn("Book a call", body, "a sample is the skill's own output: no call to action")


class Colour(unittest.TestCase):
    def test_selection_and_focus_print_in_ink_not_green(self) -> None:
        css = re.search(r"<style>(.*?)</style>", (ACME / "customer-signal-digest.html").read_text(), re.S).group(1)
        self.assertLess(css.index("::selection{background:var(--landed)"), css.index("::selection{background:var(--t1)"))
        self.assertLess(css.index("outline:2px solid var(--landed)"), css.index(":focus-visible{outline-color:var(--t1)}"))

    def test_decider_is_an_org_chart_role(self) -> None:
        roles = {"Head of Product, Quoting squad", "Lead, Quoting squad", "Tech lead, Quoting squad", "Product manager, Quoting squad"}
        self.assertIn(json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]["decides"], roles)


class Sample(unittest.TestCase):
    def test_readme_command_reproduces_the_committed_files(self) -> None:
        readme = (ROOT / "README.md").read_text()
        self.assertIn("python3 examples/acme/sample.py", readme)
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            run_sample(into)
            for rel in ("customer-signal-digest.html", "customer-signal-digest.md", "landing/quote-drafting.json"):
                with self.subTest(rel):
                    self.assertEqual((into / rel).read_bytes(), (ACME / rel).read_bytes())

    def test_page_is_self_contained(self) -> None:
        page = (ACME / "customer-signal-digest.html").read_text()
        self.assertNotRegex(page, r"<script|<link|src=\"http|url\(http|@import")
        self.assertIn('<span class="sk-ill">Illustrative</span>', page)
        self.assertIn(":root{--ill:#74A5DA}", page, "the Illustrative tag is blue")
        self.assertNotIn('class="ill"', page, "the template's grey tag")

    def test_brass_only_for_the_person_who_decides(self) -> None:
        body = re.sub(r"<style>.*?</style>", "", (ACME / "customer-signal-digest.html").read_text(), flags=re.S)
        # Inline, brass paints only the four-bar mark's person line, which carries no text.
        uses = re.findall(r"<[^>]*var\(--brass\)[^>]*>([^<]*)", body)
        self.assertEqual([u for u in uses if u], [])
        # The stylesheet gives brass to the next step's box and its owner; the owner is the brief's decider.
        self.assertEqual(body.count('<div class="next">'), 1)
        self.assertEqual(re.findall(r'<span class="o">([^<]*)</span>', body), ["Head of Product, Quoting squad"])
        self.assertIn('<span class="d">2026-12-10</span>', body)

    def test_feedback_is_what_make_sample_writes(self) -> None:
        before = {p.name: p.read_bytes() for p in (ACME / "feedback").iterdir()}
        subprocess.run([sys.executable, str(ROOT / "evals" / "make_sample.py")], check=True, capture_output=True)  # noqa: S603
        after = {p.name: p.read_bytes() for p in (ACME / "feedback").iterdir()}
        self.assertEqual(before, after)

    def test_quotes_are_redacted(self) -> None:
        page = (ACME / "customer-signal-digest.html").read_text()
        for leak in ("Priya", "Nadia Brennan", "604-555-0142", "4111 1111", "@harbourplumbing", "Sam Whitfield"):
            self.assertNotIn(leak, page)


class Brief(unittest.TestCase):
    def _folder(self, t: str, brief_text: str | None = None) -> Path:
        into = Path(t)
        (into / "briefs").mkdir()
        (into / "landing").mkdir()
        shutil.copy(ACME / "briefs" / "quote-drafting.md", into / "briefs")
        shutil.copy(ACME / "upstream" / "quote-drafting.json", into / "landing")
        if brief_text is not None:
            (into / "briefs" / "quote-drafting.md").write_text(brief_text)
        return into

    def test_edited_brief_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            into = self._folder(t, (ACME / "briefs" / "quote-drafting.md").read_text().replace("40%", "35%"))
            before = (into / "landing" / "quote-drafting.json").read_bytes()
            err = io.StringIO()
            with redirect_stderr(err):
                rc = digest.main(build_argv(into))
            self.assertEqual(rc, 2)
            self.assertIn("changed after the record opened", err.getvalue())
            self.assertEqual((into / "landing" / "quote-drafting.json").read_bytes(), before)

    def test_incomplete_brief_is_refused_by_the_parser(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            (into / "b.md").write_text("# X\n\n## Landing brief\n\n- **Problem:** Something.\n")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = digest.main(build_argv(into, "--brief", str(into / "b.md")))
            self.assertEqual(rc, 2)
            self.assertIn("not complete", err.getvalue())
            self.assertFalse((into / "landing").exists())

    def test_new_record_gets_schema_bet_and_brief(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            into = Path(t)
            (into / "briefs").mkdir()
            shutil.copy(ACME / "briefs" / "quote-drafting.md", into / "briefs")
            feed = ACME / "feedback"
            with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
                digest.main(["build", "--run", tmp, "--as-of", "2026-11-26", "--themes", str(feed / "themes.json"),
                             "--csv", f"source=nps,kind=nps,file={feed / 'nps.csv'},id=response_id,date=submitted_at,text=comment,score=score",
                             "--loop", str(into), "--bet", "quote-drafting", "--brief", str(into / "briefs" / "quote-drafting.md")])  # fmt: skip
            rec = json.loads((into / "landing" / "quote-drafting.json").read_text())
            self.assertEqual(list(rec), ["schema", "bet", "brief", "signals"])
            self.assertEqual(rec["brief"]["path"], "briefs/quote-drafting.md")
            self.assertIsNone(rec["signals"]["bet_status"]["status"])


if __name__ == "__main__":
    unittest.main()
