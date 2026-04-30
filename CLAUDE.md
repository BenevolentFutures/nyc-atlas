# nyc_atlas

Single-file browser-based educational tool for Manhattan + Brooklyn neighborhoods. Quiz modes (area→name MC, area→name typed, name→area), free exploration with mastery loop. GregorOvich-framed: the wizard at the end of time, teaching the territory of the reality you're playing.

Atlas-engine framing: this is v1 of an atlas engine. Internal modules use `atlas*` prefix and an `AtlasConfig` shape so future atlases (subway, RA venue map, ship's-log spatial map, etc.) cost hours instead of days.

Plan: `/Users/atin/.claude/plans/transient-drifting-tarjan.md`
Trident review pack: `/Users/atin/.claude/plans/transient-drifting-tarjan-review-pack-2026-04-30T0003/`

---

## Data Contract (Phase 0 record — 2026-04-30)

**Source:** Pediacities NYC Neighborhoods (created by Ontodia / NYCpedia).

**Mirror used:** `https://raw.githubusercontent.com/harsha2010/magellan/master/examples/datasets/NYC-NEIGHBORHOODS/neighborhoods.geojson`

The canonical `data.beta.nyc` and `data.dathere.com` URLs return Cloudflare challenge pages from `curl`; the `magellan` example dataset is a faithful copy of the Pediacities GeoJSON with the same schema and feature count. The `@id` property in each feature points back to `nyc.pediacities.com` URIs, confirming provenance.

**Retrieved:** 2026-04-30
**SHA256:** `ddd82f0d2ea055bc845d927ba9cb796c1f42b0daccde5f8bef80459183a5acdf`
**License:** Open Data Commons Attribution License (per upstream Pediacities catalog).
**Raw byte size:** 1,500,963 bytes (1.43 MiB).

### Schema

- Top-level: `FeatureCollection`.
- Total features: **310** (all NYC).
- Property keys per feature: `{neighborhood, borough, boroughCode, @id}`.
  - `neighborhood`: Title-case display name (e.g. "Brooklyn Heights", "SoHo", "DUMBO").
  - `borough`: Title-case borough name. **Distinct values:** `Manhattan`, `Brooklyn`, `Queens`, `Bronx`, `Staten Island`.
  - `boroughCode`: numeric string ("1"–"5").
  - `@id`: pediacities provenance URL.
- Geometry types: **`Polygon` only** for Manhattan+Brooklyn subset (108 features). No `MultiPolygon`, no interior rings (holes).

### Filter

`features` where `borough in {"Manhattan", "Brooklyn"}` (Title-case).

| Borough   | Feature count |
|-----------|---------------|
| Manhattan | 37            |
| Brooklyn  | 71            |
| **Total** | **108**       |

### Curation (`data/edits.json`)

Pediacities is GIS-correct but not always quiz-correct. The curation overlay handles:

1. **Jamaica Bay** appears 14 times in Brooklyn (small island/marsh features). Excluded — not a teachable neighborhood.
2. **Marine Park** appears 3 times. Merged to one feature; kept (it's a real Brooklyn neighborhood as well as a park).
3. **Park-only features excluded:** `Central Park`, `Prospect Park`, `Green-Wood Cemetery`, `Floyd Bennett Field`, `Plum Beach`, `Bergen Beach` (latter is mostly water).
4. **Tiny islands kept:** Ellis Island, Liberty Island, Governors Island, Randall's Island, Roosevelt Island. They're places people know.
5. **Aliases** (in `data/aliases.json`): SoHo / NoHo / Bed-Stuy / DUMBO / LES / UWS / UES / BK Heights / Park Slope / etc.

After curation, expected feature count: ~30 Manhattan + ~55 Brooklyn = **~85 features**.

### Build invariants asserted by `scripts/build_data.py`

- `borough` field present on every feature.
- `neighborhood` field present and non-empty.
- All borough values within `{Manhattan, Brooklyn, Queens, Bronx, Staten Island}`.
- All geometry types within `{Polygon, MultiPolygon}`.
- No empty coordinate arrays.
- Manhattan + Brooklyn count within ±20% of recorded baseline (108).
- After simplification at tolerance `0.0001°`, no feature becomes invalid.

Build fails loudly if any invariant breaks.

---

## Architecture

See plan for full detail. Quick map:

- `index.html` — generated single-file deliverable, no runtime network requests.
- `index.template.html` — source template with `// <<<NEIGHBORHOODS>>>`, `// <<<ALIASES>>>`, `// <<<META>>>` markers.
- `scripts/build_data.py` — discover → assert → filter → simplify → adjacency → embed.
- `data/neighborhoods.raw.geojson` — Pediacities source, COMMITTED (reproducibility).
- `data/neighborhoods.curated.geojson` — filtered + simplified + adjacency.
- `data/aliases.json` — fuzzy-match aliases.
- `data/edits.json` — curation overlay (rename / merge / exclude / override).
- `tests/match.test.js` — fuzzy matcher unit tests (Bucket 0).
- `tests/quiz.test.js` — quiz state-machine unit tests (Bucket 0).
- `tests/build_data_test.py` — pipeline smoke test (Bucket 0).
- `tests/browser_validation.md` — Buckets A/B/C run record.
- `tests/screenshots/` — Bucket B screenshots.

Internal `index.html` modules: `atlasGeo`, `atlasRender`, `atlasMatch`, `atlasQuiz`, `atlasMastery`, `atlasVoice`, `atlasStorage`, `atlasApp`. All under one `<script>` block, separated by `/* === module === */` markers.

## Build & test

```bash
cd projects/nyc_atlas

# build the deliverable
python3 scripts/build_data.py

# unit tests (Bucket 0)
node --test tests/
python3 -m pytest tests/

# open the deliverable
open index.html
```

## Browser support

- Latest Safari (macOS) and latest Chromium-based browser (Chrome / Edge / Arc): **fully validated**.
- Firefox: best-effort; not in the validation suite.
- localStorage on Safari `file://` is unreliable — when unavailable, in-memory fallback keeps the session functional but unable to persist scores between reloads. The intro-replay glyph is always shown so the wizard's framing is reachable.

## Visibility

Public-friendly — no personal data. Hostable as a static file anywhere.
