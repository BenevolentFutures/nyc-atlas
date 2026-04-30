#!/usr/bin/env python3
"""Build script for nyc_atlas.

Pipeline: discover -> assert -> filter -> apply edits -> simplify -> adjacency ->
emit curated GeoJSON + metadata -> inject into index.template.html -> write index.html.

Idempotent: always writes index.html from the template; never patches in place.
Run from the project root: ``python3 scripts/build_data.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid


# ----- paths -----------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
LIB_DIR = PROJECT_DIR / "lib"
RAW_PATH = DATA_DIR / "neighborhoods.raw.geojson"
CURATED_PATH = DATA_DIR / "neighborhoods.curated.geojson"
EDITS_PATH = DATA_DIR / "edits.json"
ALIASES_PATH = DATA_DIR / "aliases.json"
MATCH_MODULE_PATH = LIB_DIR / "match.js"
TEMPLATE_PATH = PROJECT_DIR / "index.template.html"
OUTPUT_PATH = PROJECT_DIR / "index.html"

# ----- config ----------------------------------------------------------------

INCLUDE_BOROUGHS = {"Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"}
SIMPLIFY_TOLERANCE = 0.0002  # ~22m at NYC latitudes (relaxed from 0.0001 to keep all-5 file size sane)
OUTLINE_SIMPLIFY_TOLERANCE = 0.0003
ADJACENCY_BUFFER = 0.0008    # ~90m, captures water-separated pairs (Brooklyn Hts <-> FiDi)
COORDINATE_PRECISION = 5     # decimal places after simplification

SOURCE_URL = (
    "https://raw.githubusercontent.com/harsha2010/magellan/master/"
    "examples/datasets/NYC-NEIGHBORHOODS/neighborhoods.geojson"
)
SOURCE_NAME = "Pediacities NYC Neighborhoods (via magellan example mirror)"
SOURCE_LICENSE = "Open Data Commons Attribution License"


# ----- helpers ---------------------------------------------------------------

def slugify(name: str) -> str:
    """Generate URL-safe id for a neighborhood name."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def round_coords(geom_mapping: dict, precision: int) -> dict:
    """Recursively round coordinates in a GeoJSON geometry mapping."""
    def _round(coords):
        if isinstance(coords, (list, tuple)):
            if coords and isinstance(coords[0], (int, float)):
                return [round(c, precision) for c in coords]
            return [_round(c) for c in coords]
        return coords

    out = dict(geom_mapping)
    out["coordinates"] = _round(geom_mapping["coordinates"])
    return out


def assert_schema(features: list[dict]) -> None:
    """Fail loudly if the source schema has drifted."""
    if not features:
        sys.exit("FAIL: no features in raw geojson")

    valid_borough_values = {"Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"}
    valid_geom_types = {"Polygon", "MultiPolygon"}

    for i, feat in enumerate(features):
        props = feat.get("properties", {})
        if "borough" not in props:
            sys.exit(f"FAIL: feature {i} missing 'borough' property")
        if "neighborhood" not in props or not props["neighborhood"]:
            sys.exit(f"FAIL: feature {i} missing or empty 'neighborhood' property")
        if props["borough"] not in valid_borough_values:
            sys.exit(f"FAIL: feature {i} has unexpected borough '{props['borough']}'")

        geom = feat.get("geometry", {})
        if geom.get("type") not in valid_geom_types:
            sys.exit(f"FAIL: feature {i} has unsupported geometry '{geom.get('type')}'")
        if not geom.get("coordinates"):
            sys.exit(f"FAIL: feature {i} has empty coordinates")

    print(f"  schema OK: {len(features)} raw features pass invariants")


def apply_edits(
    features: list[dict],
    edits: dict,
) -> list[dict]:
    """Apply curation overlay: exclude, merge duplicates, rename."""
    excludes = edits.get("exclude", [])
    merges = edits.get("merge_duplicates", [])
    renames = edits.get("rename", [])

    # Build exclude lookup (borough, neighborhood) -> True
    exclude_keys = {
        (e["borough"], e["neighborhood"]) for e in excludes
    }

    kept = []
    excluded_count = 0
    for feat in features:
        key = (feat["properties"]["borough"], feat["properties"]["neighborhood"])
        if key in exclude_keys:
            excluded_count += 1
            continue
        kept.append(feat)
    print(f"  excluded {excluded_count} features per edits.json")

    # Merge duplicates: same (borough, neighborhood) -> keep_largest
    by_key: dict[tuple[str, str], list[dict]] = {}
    for feat in kept:
        k = (feat["properties"]["borough"], feat["properties"]["neighborhood"])
        by_key.setdefault(k, []).append(feat)

    merge_strategies = {
        (m["borough"], m["neighborhood"]): m["strategy"]
        for m in merges
    }

    deduped = []
    merged_count = 0
    for k, group in by_key.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        strategy = merge_strategies.get(k, "keep_largest")
        if strategy == "keep_largest":
            best = max(group, key=lambda f: shape(f["geometry"]).area)
            deduped.append(best)
            merged_count += len(group) - 1
        elif strategy == "union":
            geoms = [shape(f["geometry"]) for f in group]
            unioned = unary_union(geoms)
            new_feat = dict(group[0])
            new_feat["geometry"] = mapping(unioned)
            deduped.append(new_feat)
            merged_count += len(group) - 1
        else:
            # Default: keep all (shouldn't happen given our edits.json)
            deduped.extend(group)
    if merged_count:
        print(f"  merged {merged_count} duplicate features")

    # Renames (none in v1, but pattern is here)
    rename_map = {(r["borough"], r["from"]): r["to"] for r in renames}
    for feat in deduped:
        k = (feat["properties"]["borough"], feat["properties"]["neighborhood"])
        if k in rename_map:
            feat["properties"]["neighborhood"] = rename_map[k]

    return deduped


def simplify_features(features: list[dict]) -> list[dict]:
    """Simplify polygons; preserve topology; drop coordinate precision."""
    out = []
    invalid_count = 0
    for feat in features:
        geom = shape(feat["geometry"])
        simplified = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        if not simplified.is_valid or simplified.is_empty:
            invalid_count += 1
            print(f"  WARN: {feat['properties']['neighborhood']} became invalid after simplify; falling back to raw")
            simplified = geom
        new_feat = dict(feat)
        new_feat["geometry"] = round_coords(mapping(simplified), COORDINATE_PRECISION)
        out.append(new_feat)
    if invalid_count:
        print(f"  {invalid_count} features fell back to unsimplified geometry")
    else:
        print(f"  simplified {len(out)} features at tolerance {SIMPLIFY_TOLERANCE}")
    return out


def compute_metadata(features: list[dict]) -> list[dict]:
    """Add slug, centroid, bbox to each feature's properties."""
    for feat in features:
        props = feat["properties"]
        geom = shape(feat["geometry"])
        props["id"] = slugify(props["neighborhood"])
        cx, cy = geom.centroid.x, geom.centroid.y
        props["centroid"] = [round(cx, COORDINATE_PRECISION), round(cy, COORDINATE_PRECISION)]
        minx, miny, maxx, maxy = geom.bounds
        props["bbox"] = [
            round(minx, COORDINATE_PRECISION),
            round(miny, COORDINATE_PRECISION),
            round(maxx, COORDINATE_PRECISION),
            round(maxy, COORDINATE_PRECISION),
        ]
    return features


def compute_adjacency(features: list[dict]) -> list[dict]:
    """Compute neighbors via shapely.touches() with small buffer.

    Uses a buffered-intersection check so water-separated neighborhoods
    (Brooklyn Heights <-> Lower Manhattan) still register as neighbors
    when their shores are close enough.

    Buffers are computed against valid geometries (make_valid). Topology
    errors on individual pairs are tolerated — the buffer-distance check
    is the fallback for any pair that fails direct touch().
    """
    def _safe(g):
        if g.is_valid:
            return g
        fixed = make_valid(g)
        return fixed if fixed.is_valid else g

    geoms = [(feat["properties"]["id"], _safe(shape(feat["geometry"]))) for feat in features]

    skipped = 0
    for feat in features:
        my_id = feat["properties"]["id"]
        my_geom = _safe(shape(feat["geometry"]))
        try:
            my_buffered = my_geom.buffer(ADJACENCY_BUFFER)
        except Exception:
            my_buffered = None

        neighbors = []
        for other_id, other_geom in geoms:
            if other_id == my_id:
                continue
            try:
                touches = my_geom.touches(other_geom)
            except Exception:
                touches = False
            try:
                near = (my_buffered is not None) and my_buffered.intersects(other_geom)
            except Exception:
                near = False
                skipped += 1
            if touches or near:
                neighbors.append(other_id)
        feat["properties"]["neighbors"] = sorted(neighbors)

    avg_neighbors = sum(len(f["properties"]["neighbors"]) for f in features) / max(len(features), 1)
    print(f"  adjacency computed; avg {avg_neighbors:.1f} neighbors per feature"
          + (f" ({skipped} pair errors tolerated)" if skipped else ""))
    return features


def load_match_module() -> str:
    """Load lib/match.js and strip ES-module syntax for inline injection."""
    src = MATCH_MODULE_PATH.read_text()
    # Strip leading `export ` from each function/const declaration.
    src = re.sub(r"^export\s+", "", src, flags=re.MULTILINE)
    # Trim trailing whitespace.
    return src.strip()


def compute_outlines(features: list[dict]) -> dict:
    """Compute borough-union and NYC-union outlines for orientation layers.

    Returns a dict with `boroughs: {borough_name: GeoJSON geometry}` and
    `nyc: GeoJSON geometry` — both simplified for compact embedding.
    """
    by_borough: dict[str, list] = {}
    for f in features:
        b = f["properties"]["borough"]
        try:
            geom = shape(f["geometry"])
            if not geom.is_valid:
                geom = make_valid(geom)
            by_borough.setdefault(b, []).append(geom)
        except Exception:
            continue

    borough_outlines = {}
    borough_label_points = {}
    all_geoms = []
    for b, geoms in by_borough.items():
        try:
            unioned = unary_union(geoms)
            simplified = unioned.simplify(OUTLINE_SIMPLIFY_TOLERANCE, preserve_topology=True)
            if simplified.is_empty or not simplified.is_valid:
                continue
            borough_outlines[b] = round_coords(mapping(simplified), COORDINATE_PRECISION)
            # Use representative_point() — guaranteed to be inside the polygon
            # (centroid of disconnected boroughs like SI lands in water otherwise).
            try:
                rep = simplified.representative_point()
                borough_label_points[b] = [round(rep.x, COORDINATE_PRECISION), round(rep.y, COORDINATE_PRECISION)]
            except Exception:
                c = simplified.centroid
                borough_label_points[b] = [round(c.x, COORDINATE_PRECISION), round(c.y, COORDINATE_PRECISION)]
            all_geoms.append(unioned)
        except Exception as e:
            print(f"  WARN: outline for {b} failed: {e}")

    nyc_outline = None
    if all_geoms:
        try:
            unioned_all = unary_union(all_geoms)
            simplified_all = unioned_all.simplify(OUTLINE_SIMPLIFY_TOLERANCE * 1.5, preserve_topology=True)
            nyc_outline = round_coords(mapping(simplified_all), COORDINATE_PRECISION)
        except Exception as e:
            print(f"  WARN: NYC outline failed: {e}")

    print(f"  outlines computed: {len(borough_outlines)} boroughs + {'NYC' if nyc_outline else 'no NYC'}")
    return {"boroughs": borough_outlines, "labels": borough_label_points, "nyc": nyc_outline}


def inject_template(template_text: str, replacements: dict[str, str]) -> str:
    """Replace marker comments with embedded JS literals.

    Markers: ``// <<<NEIGHBORHOODS>>>``, ``// <<<ALIASES>>>``, ``// <<<META>>>``.
    Fail loudly if a marker is missing.
    """
    out = template_text
    for marker, payload in replacements.items():
        token = f"// <<<{marker}>>>"
        if token not in out:
            sys.exit(f"FAIL: template missing marker {token}")
        out = out.replace(token, payload)
    return out


# ----- main ------------------------------------------------------------------

def main() -> None:
    print(f"=== nyc_atlas build  ({date.today().isoformat()}) ===")
    print()

    if not RAW_PATH.exists():
        sys.exit(f"FAIL: raw geojson not found at {RAW_PATH}")
    if not TEMPLATE_PATH.exists():
        sys.exit(f"FAIL: template not found at {TEMPLATE_PATH}")

    raw_bytes = RAW_PATH.read_bytes()
    raw_size = len(raw_bytes)
    sha = hashlib.sha256(raw_bytes).hexdigest()
    raw = json.loads(raw_bytes)

    print(f"raw geojson: {RAW_PATH}")
    print(f"  bytes: {raw_size:,}  sha256: {sha[:12]}...")
    print()

    print("schema assertions:")
    assert_schema(raw["features"])
    print()

    print("filter to Manhattan + Brooklyn:")
    filtered = [f for f in raw["features"] if f["properties"]["borough"] in INCLUDE_BOROUGHS]
    by_b = {b: 0 for b in INCLUDE_BOROUGHS}
    for f in filtered:
        by_b[f["properties"]["borough"]] += 1
    for b, n in by_b.items():
        print(f"  {b}: {n}")
    print(f"  total filtered: {len(filtered)}")
    print()

    print("apply edits.json overlay:")
    edits = json.loads(EDITS_PATH.read_text())
    curated = apply_edits(filtered, edits)
    print(f"  after edits: {len(curated)} features")
    print()

    print("simplify polygons:")
    curated = simplify_features(curated)
    print()

    print("compute slug + centroid + bbox:")
    curated = compute_metadata(curated)
    print()

    print("compute adjacency (build-time):")
    curated = compute_adjacency(curated)
    print()

    print("compute orientation outlines:")
    outlines = compute_outlines(curated)
    print()

    # Strip noisy keys we don't need at runtime
    keep_keys = {"id", "neighborhood", "borough", "centroid", "bbox", "neighbors"}
    for feat in curated:
        feat["properties"] = {k: v for k, v in feat["properties"].items() if k in keep_keys}

    final_by_b = {b: 0 for b in INCLUDE_BOROUGHS}
    for f in curated:
        final_by_b[f["properties"]["borough"]] += 1

    # Emit curated GeoJSON
    curated_collection = {"type": "FeatureCollection", "features": curated}
    curated_json = json.dumps(curated_collection, separators=(",", ":"))
    CURATED_PATH.write_text(curated_json)
    curated_size = CURATED_PATH.stat().st_size
    print(f"curated geojson: {CURATED_PATH}")
    print(f"  bytes: {curated_size:,}  features: {len(curated)}")
    print(f"  Manhattan: {final_by_b['Manhattan']}  Brooklyn: {final_by_b['Brooklyn']}")
    print()

    # Compute metadata payload
    meta = {
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "license": SOURCE_LICENSE,
        "retrieved": date.today().isoformat(),
        "raw_sha256": sha,
        "raw_bytes": raw_size,
        "curated_bytes": curated_size,
        "simplification_tolerance": SIMPLIFY_TOLERANCE,
        "feature_counts": final_by_b,
    }

    # Load aliases
    aliases = json.loads(ALIASES_PATH.read_text())["aliases"]

    # Inject into template
    print("inject into template:")
    template = TEMPLATE_PATH.read_text()
    match_module = load_match_module()
    output = inject_template(
        template,
        {
            "NEIGHBORHOODS": json.dumps(curated_collection, separators=(",", ":")),
            "ALIASES": json.dumps(aliases, separators=(",", ":")),
            "META": json.dumps(meta, separators=(",", ":")),
            "OUTLINES": json.dumps(outlines, separators=(",", ":")),
            "MATCH_MODULE": match_module,
        },
    )
    OUTPUT_PATH.write_text(output)
    output_size = OUTPUT_PATH.stat().st_size
    print(f"  wrote {OUTPUT_PATH}")
    print(f"  bytes: {output_size:,}")
    print()

    print("=== done ===")
    if output_size > 1_000_000:
        print(f"WARN: index.html is {output_size:,} bytes (> 1 MB target)")


if __name__ == "__main__":
    main()
