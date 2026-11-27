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
        """Every number on the page's cover facts is a figure value in the key."""
        key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]
        page = (ACME / "customer-signal-digest.html").read_text()
        facts = re.findall(r"<span><b>([^<]+)</b>", page)
        values = {str(d["value"]) for _, d in walk(key) if isinstance(d, dict) and "value" in d} | {
            f"{d['value']:g}%" for _, d in walk(key) if isinstance(d, dict) and d.get("unit") == "%"
        }
        for f in facts:
            with self.subTest(f):
                self.assertIn(f.replace(",", ""), values)


class StatusWords(unittest.TestCase):
    def test_status_words_only_from_landed_status(self) -> None:
        key = json.loads((ACME / "landing" / "quote-drafting.json").read_text())["signals"]
        hits = [p for p, v in walk(key) if isinstance(v, str) and STATUS.search(v)]
        # bet_status.value is the copy; printed_from and the copied figure's source name where it came from.
        self.assertEqual([p for p in hits if p not in ("bet_status.status", "bet_status.printed_from")], [])

    def test_page_prints_status_once_in_its_mark(self) -> None:
        page = (ACME / "customer-signal-digest.html").read_text()
        body = re.sub(r"<style>.*?</style>", "", page, flags=re.S)
        body = body.replace('<span class="st landed">landed</span>', "")
        body = body.replace("landed.status", "")
        self.assertEqual(STATUS.findall(re.sub(r"<[^>]+>", " ", body)), [])

    def test_markdown_prints_status_once(self) -> None:
        md = (ACME / "customer-signal-digest.md").read_text().replace("landed.status", "")
        self.assertEqual(STATUS.findall(md), ["landed"])

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
        self.assertIn('class="ill"', page)

    def test_brass_only_for_the_person_who_decides(self) -> None:
        body = re.sub(r"<style>.*?</style>", "", (ACME / "customer-signal-digest.html").read_text(), flags=re.S)
        uses = re.findall(r"[^<>]{0,0}<[^>]*var\(--brass\)[^>]*>([^<]*)", body)
        self.assertEqual([u for u in uses if u], ["Decides: Head of Product, Quoting squad"])

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
