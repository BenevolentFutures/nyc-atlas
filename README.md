# nyc_atlas

A single-file browser-based educational tool for the neighborhoods of Manhattan and Brooklyn. Hover, click, quiz yourself, watch the territory light up as you earn it.

Open `index.html` in any modern browser. No server, no internet, no install.

## Run it

```bash
open index.html
```

That's it.

## Modes

- **D — Free exploration.** Hover (or tap on touch) to learn. Mastered neighborhoods glow brighter. The map fills in as you walk.
- **A — Multiple choice.** A neighborhood lights up. Pick its name from four options.
- **B — Type the name.** A neighborhood lights up. Type it. Aliases like `bk heights`, `bed-stuy`, `soho`, `dumbo` are accepted.
- **C — Find the area.** A name appears. Click the right neighborhood on the map.

Pick borough scope (Both / Manhattan / Brooklyn) and round length (5 / 10 / 25 / Endless) before each round.

## Build it

If you want to refresh data or rebuild from source:

```bash
# from projects/nyc_atlas/
python3 scripts/build_data.py
```

The script downloads Pediacities (cached locally), filters to Manhattan + Brooklyn, applies the curation overlay (`data/edits.json`), simplifies polygons, computes adjacency, and injects the curated data into `index.template.html` to produce `index.html`.

Dependencies: `python3` with `shapely` and `requests`. Install via `pip install shapely requests` if needed.

## Test it

```bash
# unit tests (pure logic — fuzzy matcher, build pipeline)
node --test tests/match.test.js
python3 -m pytest tests/

# browser validation (run scenarios from tests/browser_validation.md against open index.html)
```

## Browser support

Latest Safari (macOS) and Chromium-based (Chrome / Edge / Arc). Firefox best-effort. localStorage on Safari `file://` may not persist; sessions still work, just don't carry scores across reloads.

## About the data

Boundaries: [Pediacities NYC Neighborhoods](http://nyc.pediacities.com) (Open Data Commons Attribution License), retrieved via the [magellan](https://github.com/harsha2010/magellan) example mirror on 2026-04-30. 108 raw features across Manhattan + Brooklyn; ~85 after curation (parks and water-only features removed). Curation overlay lives in `data/edits.json` — Pediacities is opinionated cultural geography, and the wizard's atlas is allowed to disagree with the source on small things.

Aliases (`data/aliases.json`) catch the common nicknames and abbreviations New Yorkers actually say.

## Voice

The wizard appears at thresholds: opening invocation, between-round beats, milestone moments, end-of-round reflection. He stays out of the chrome. The map is the work; he's the company you're keeping while you learn it.

---

*Atlas engine v1. NYC is the first map. There may be others.*
