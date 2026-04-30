# Browser validation — `nyc_atlas`

Three-bucket test record. Run once per significant change. All three buckets must be green for the project to be considered done.

Run dates:
- 2026-04-30 — initial validation pass — all green.

---

## Bucket 0 — Unit tests (pure logic)

```bash
node --test tests/match.test.js    # 12 cases
python3 -m pytest tests/           # build_data_test.py → 13 cases
```

**Status:** all 25 tests pass.

| Suite                       | Cases | Pass | Fail |
|-----------------------------|------:|-----:|-----:|
| `tests/match.test.js`       |    12 |   12 |    0 |
| `tests/build_data_test.py`  |    13 |   13 |    0 |

---

## Bucket A — Automated browser assertions

Run via c11-browser MCP against `file://.../index.html`. All probes go through `window.__atlas`.

| #  | Test                                                                      | Status | Notes |
|----|---------------------------------------------------------------------------|:-----:|-------|
| 1  | Page loads, polygon count = 84 (36 Manhattan + 48 Brooklyn)                | ✓ | Matches `ATLAS_META.feature_counts` |
| 2  | Zero external network refs (`getExternalResourceRefs().length === 0`)      | ✓ | No CDN, no external fonts, no remote images |
| 3  | First-visit intro: `resetStorage` → reload → modal present → dismiss → reload → modal absent → click wizard glyph → modal returns | ✓ | `seen_intro` flag respected; replay glyph works |
| 4  | Mode D click: flavor card shows correct name + borough + mastery state     | ✓ | Card element rendered with `name`, `meta` |
| 5  | Mode A: forceQuestion(SoHo); submit('SoHo') → correct=true, score++; submit wrong → correct=false, score unchanged | ✓ | Adjacency-aware distractors visible (NoHo, Greenwich Village, Chinatown for SoHo) |
| 6  | Mode B fuzzy: `match.test('soho','SoHo')` ✓; `match.test('NoHo','SoHo')` ✗; `match.test('williamsbrg','Williamsburg')` ✓; `match.test('SoHoo','SoHo')` ✗ (len<5 → exact only); `match.test('bk heights','Brooklyn Heights')` ✓ via alias | ✓ | All 9 cases match expectations |
| 7  | Mode C: forceQuestion(Park Slope); clickByName('park-slope') → score++; clickByName('soho') for Bushwick target → score unchanged | ✓ | Wrong polygon flashes red; correct brightens |
| 8  | Borough filter: scope=Brooklyn → `getQuestionPool()` size 48; no Manhattan names leak; scope=Manhattan → 36; no Brooklyn leaks | ✓ | Both directions verified |
| 9  | Round length: 5-question round → reflection modal opens after 5; stats read "5 / 5 · 100% accuracy"; bestScores updated | ✓ | `nyc_atlas:scores` key updated with `mode:scope:length` keys |
| 10 | Score persistence: complete round, reload, `getScores()` retains best scores; `getMastery()` retains counts; `seenIntro=true` | ✓ | localStorage versioned via `nyc_atlas:version` |
| 11 | Adjacency-aware distractors: `getFeatureState('West Village').neighbors` = `['chelsea','greenwich-village','soho']` | ✓ | Real geographic neighbors |
| 12 | Resize: dispatch resize event; polygons re-render; no errors thrown; polygon count unchanged | ✓ | Debounced 150ms via `setTimeout` |
| 13 | Open from `file://` works without a server                                  | ✓ | macOS `open index.html` opens it |
| 14 | Mastery loop: 3× submit('SoHo') correct → `getMastery().soho === 3`; switch to Mode D → SoHo polygon class includes "mastered" | ✓ | First-mastery flag fires on threshold crossing |

**Bucket A: 14 / 14 passing.**

---

## Bucket B — Manual screenshot review (named criteria, human judge: Atin)

Screenshots in `tests/screenshots/`. Each screenshot must meet its named visual criteria.

| #  | Screenshot                  | File                              | Criteria                                                                                                    | Atin signoff |
|----|-----------------------------|-----------------------------------|-------------------------------------------------------------------------------------------------------------|:------------:|
| 15 | Intro modal                 | `07-intro-modal.png`              | Wizard text legible, serif renders cleanly, paragraph spacing right, "BEGIN" button readable                | _pending_    |
| 16 | Mode D — fresh map          | `01-mode-d-fresh.png`             | Both boroughs visible, polygons read as glowing edges (not gray haloes), data credit visible at bottom       | _pending_    |
| 17 | Mode A — target glow        | `02-mode-a-soho.png`              | SoHo glows brightly cyan; other polygons muted but visible; 4 choice buttons readable; distractors are real neighbors | _pending_    |
| 18 | Mode B — type input         | `03-mode-b-bedstuy.png`           | Bed-Stuy target glows; input + submit + skip all readable; placeholder text visible                          | _pending_    |
| 19 | Mode C — name shown         | `04-mode-c-williamsburg.png`      | "Williamsburg" displays in serif; map shows all polygons in resting state (no target highlighted)             | _pending_    |
| 20 | End-of-round modal          | `05-reflection-modal.png`         | Wizard reflection line + "4 / 5 · 80% ACCURACY" + "WALK AGAIN" button all legible                            | _pending_    |
| 21 | Mode D — mastery loop       | `06-mastery-mode-d.png`           | Mastered neighborhoods glow softly (cyan), un-mastered ones dim; clear visual contrast; "13/84 mastered" header | _pending_    |

---

## Bucket C — Atin's product acceptance

| #  | Test                                                                                              | Atin signoff |
|----|---------------------------------------------------------------------------------------------------|:------------:|
| 22 | Play one round of Mode A at length 10. The map feels right; mode is not broken.                    | _pending_    |
| 23 | Play one round of Mode B at length 10. Fuzzy match feels forgiving but not loose.                  | _pending_    |
| 24 | Play one round of Mode C at length 10. Spatial recall feels honest.                                | _pending_    |
| 25 | Spend 3+ minutes in Mode D. The wizard's framing reads. Mastery lights up the territory you've earned. | _pending_    |
| 26 | The four threshold voice moments (intro, between-round beats, mastery acks, reflection) land well.   | _pending_    |

---

## Notes

- **Test seam (`window.__atlas`)** is part of every shipped `index.html`. It is a small, harmless object that gives browser automation deterministic control. Not removed for the "share" version.
- **Sample size:** index.html is 151 KB. Well under the 1 MB target. Most of that is the curated GeoJSON; CSS and JS are ~25 KB combined.
- **No runtime network requests.** Verified via DOM scan and via the browser network tab during interactive testing.
- **Browsers tested:** c11 embedded WKWebView (macOS). Latest Safari and Chromium browsers should also work; Firefox is best-effort.
- **localStorage on `file://`:** Safari has historically dropped writes here. The atlas wraps localStorage in try/catch with an in-memory fallback. The intro-replay glyph (∴) means even if persistence fails, the wizard's framing is reachable on every load.
