# Changelog

## 0.3.1, 2026-11-27

- The HTML page follows the Landing Loop sample anatomy: the shared header (mark, DACARD, skill, date, version, blue Illustrative tag), the verdict as the heading ("Quote drafting landed, but 7 customer accounts still raise the problem."), the project's status from did-it-land beside the customer check, the signature picture, one next step with the brief's decider in brass and a due date, then the quotes and the figures in two columns. Other themes fold away; the evidence ledger, sources, ranks, file names and the record key fold under "For your engineers".
- The signature picture: two stacks of signals, "still feel the problem" against "problem gone", one block per signal, the last 30 days in ink. A 640 wide variant for desktop and a 340 wide one for phones; the aria-label states the answer. Drawn with svgkit, vendored byte-identical from landing-loop and pinned in `VENDORED.json` under `landing-loop`.
- Public copy in plain words, on the page and in the Markdown twin: project, target, landing brief (defined at first use), the project file. The record's words are unchanged.
- The Illustrative tag is the family's blue, not the template's grey.
- Tests: the picture draws only printed figures, green appears only beside the word landed, the aria-label states the answer, public copy uses the plain words, and the vendored svgkit matches its pin.

## 0.3.0, 2026-11-26

- Step 04 (Learn) of the Landing Loop. `build --loop FOLDER --bet SLUG` reads the bet's brief and the `landed` key of `landing/<bet>.json`, and writes only the `signals` key, every figure with value, unit, source, window and as_of. Every other key is kept byte for byte.
- The bet's status is printed from `landed.status`, never computed. The skill's own check says problem still raised or problem not raised.
- `themes.json` takes `"bet"` and `"side"` (problem or praise), confirmed by the person, so code never guesses which themes are about the bet.
- One HTML page for leaders in the Leader Report style, with a Markdown twin. Brass only for who decides; the illustrative tag on every sample quote.
- Live first: Zendesk and Intercom pages are read with the Leader Report's own page reader, date parser and theme rule. The brief parser, the Zendesk and Intercom collectors and the template are vendored unchanged at a pinned commit (`VENDORED.json`). CSV stays the fallback.
- `--until` closes the feedback window; signals outside it are counted as left out.
- Sample: `python3 examples/acme/sample.py` regenerates `examples/acme/customer-signal-digest.html`, its Markdown twin and the record from the canonical Acme brief, byte for byte.
- Needs Python 3.11 or later, like the other loop skills.
- Every entry script, the sample's included, stops on Python older than 3.11 before it reads or writes anything. The page is rendered before the record is written, and the sample builds in a scratch folder and moves its outputs into place only on success, so a failed run never strips the `signals` key.
- Text selection and keyboard focus print in ink, not the template's green, which is kept for landed.

## 0.1.0, 2026-11-26

- First version: redaction first, duplicates merged, themes ranked in code by reach, frequency and recency, quoted evidence with source IDs, and a check on the notes Claude writes.
