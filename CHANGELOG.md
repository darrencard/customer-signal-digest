# Changelog

## 0.3.0, 2026-11-26

- Step 04 (Learn) of the Landing Loop. `build --loop FOLDER --bet SLUG` reads the bet's brief and the `landed` key of `landing/<bet>.json`, and writes only the `signals` key, every figure with value, unit, source, window and as_of. Every other key is kept byte for byte.
- The bet's status is printed from `landed.status`, never computed. The skill's own check says problem still raised or problem not raised.
- `themes.json` takes `"bet"` and `"side"` (problem or praise), confirmed by the person, so code never guesses which themes are about the bet.
- One HTML page for leaders in the Leader Report style, with a Markdown twin. Brass only for who decides; the illustrative tag on every sample quote.
- Live first: Zendesk and Intercom pages are read with the Leader Report's own page reader, date parser and theme rule. The brief parser, the Zendesk and Intercom collectors and the template are vendored unchanged at a pinned commit (`VENDORED.json`). CSV stays the fallback.
- `--until` closes the feedback window; signals outside it are counted as left out.
- Sample: `python3 examples/acme/sample.py` regenerates `examples/acme/customer-signal-digest.html`, its Markdown twin and the record from the canonical Acme brief, byte for byte.
- Needs Python 3.11 or later, like the other loop skills.

## 0.1.0, 2026-11-26

- First version: redaction first, duplicates merged, themes ranked in code by reach, frequency and recency, quoted evidence with source IDs, and a check on the notes Claude writes.
