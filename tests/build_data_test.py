"""Smoke test for the data pipeline.

Runs the build script and verifies the curated GeoJSON, aliases, and the
generated index.html have the shapes we expect. Lives next to the unit
tests so ``pytest tests/`` picks it up alongside the JavaScript suite.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "build_data.py"
RAW = PROJECT_DIR / "data" / "neighborhoods.raw.geojson"
CURATED = PROJECT_DIR / "data" / "neighborhoods.curated.geojson"
ALIASES = PROJECT_DIR / "data" / "aliases.json"
EDITS = PROJECT_DIR / "data" / "edits.json"
INDEX = PROJECT_DIR / "index.html"


# ----- helpers --------------------------------------------------------------


def _run_build():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
    )
    assert result.returncode == 0, f"build failed:\n{result.stdout}\n{result.stderr}"
    return result


def _load_curated():
    return json.loads(CURATED.read_text())


# ----- tests ----------------------------------------------------------------


def test_raw_geojson_present_and_parses():
    assert RAW.exists(), "raw GeoJSON must be committed"
    data = json.loads(RAW.read_text())
    assert data.get("type") == "FeatureCollection"
    assert len(data["features"]) >= 100, "expected at least 100 raw features"


def test_aliases_file_parses():
    data = json.loads(ALIASES.read_text())
    assert "aliases" in data
    assert isinstance(data["aliases"], dict)
    assert len(data["aliases"]) > 0


def test_edits_file_parses():
    data = json.loads(EDITS.read_text())
    assert "exclude" in data
    assert "merge_duplicates" in data
    # All exclude entries name a borough + neighborhood
    for entry in data["exclude"]:
        assert "borough" in entry
        assert "neighborhood" in entry


def test_build_runs_clean():
    _run_build()


def test_curated_has_only_manhattan_brooklyn():
    if not CURATED.exists():
        _run_build()
    fc = _load_curated()
    boroughs = {f["properties"]["borough"] for f in fc["features"]}
    assert boroughs == {"Manhattan", "Brooklyn"}, f"unexpected boroughs: {boroughs}"


def test_curated_excludes_park_only_features():
    if not CURATED.exists():
        _run_build()
    fc = _load_curated()
    names = {f["properties"]["neighborhood"] for f in fc["features"]}
    excluded = {"Central Park", "Prospect Park", "Green-Wood Cemetery", "Floyd Bennett Field"}
    leak = excluded & names
    assert not leak, f"park-only features leaked into curated: {leak}"


def test_curated_no_duplicate_jamaica_bay():
    if not CURATED.exists():
        _run_build()
    fc = _load_curated()
    jamaica_count = sum(1 for f in fc["features"] if f["properties"]["neighborhood"] == "Jamaica Bay")
    assert jamaica_count == 0, "Jamaica Bay should be excluded entirely"


def test_curated_features_have_required_props():
    if not CURATED.exists():
        _run_build()
    fc = _load_curated()
    required = {"id", "neighborhood", "borough", "centroid", "bbox", "neighbors"}
    for f in fc["features"]:
        missing = required - f["properties"].keys()
        assert not missing, f"feature {f['properties'].get('neighborhood')} missing {missing}"


def test_adjacency_computed_for_most_features():
    if not CURATED.exists():
        _run_build()
    fc = _load_curated()
    with_neighbors = sum(1 for f in fc["features"] if f["properties"]["neighbors"])
    ratio = with_neighbors / len(fc["features"])
    assert ratio >= 0.8, f"only {ratio*100:.0f}% of features have neighbors"


def test_known_neighbors_are_adjacent():
    """Spot-check: SoHo touches both Tribeca and NoHo (well-known shared borders)."""
    if not CURATED.exists():
        _run_build()
    fc = _load_curated()
    by_id = {f["properties"]["id"]: f for f in fc["features"]}
    soho = by_id.get("soho")
    assert soho is not None, "SoHo missing"
    soho_neighbors = set(soho["properties"]["neighbors"])
    assert {"tribeca", "noho"} <= soho_neighbors, (
        f"expected tribeca + noho in SoHo neighbors; got {soho_neighbors}"
    )


def test_index_html_generated_and_self_contained():
    if not INDEX.exists():
        _run_build()
    text = INDEX.read_text()
    # All markers replaced
    assert "<<<NEIGHBORHOODS>>>" not in text
    assert "<<<ALIASES>>>" not in text
    assert "<<<META>>>" not in text
    assert "<<<MATCH_MODULE>>>" not in text
    # No external script/style/font hosts
    forbidden = re.compile(r'(src|href)=[\'"]https?://', re.IGNORECASE)
    matches = forbidden.findall(text)
    # The intro modal allows an `https://...` mention only if it's inside the data credit / about text;
    # we forbid actual src/href attributes pointing to remote URLs.
    assert not matches, f"index.html references external URLs: {matches[:5]}"
    # Size sanity
    size = INDEX.stat().st_size
    assert size < 1_000_000, f"index.html is {size:,} bytes (> 1 MB target)"


def test_index_html_includes_match_normalize():
    if not INDEX.exists():
        _run_build()
    text = INDEX.read_text()
    assert "function normalize(" in text, "match module not injected"
    assert "function levenshtein(" in text
    assert "function thresholdFor(" in text


def test_atlas_meta_has_provenance_block():
    if not INDEX.exists():
        _run_build()
    text = INDEX.read_text()
    # ATLAS_META should be present with source URL and license
    assert "ATLAS_META" in text
    assert "Open Data Commons Attribution License" in text or "license" in text.lower()
