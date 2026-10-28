#!/usr/bin/env python3
"""Build the demo's curated pre-cutoff inputs (build-time step, documented).

Reads the raw temporal cascade plus the staged flood files and writes ONLY
pre-cutoff bytes into demo/nepal_cascade/inputs/. The cutoff is derived from
the data itself (the earliest snapshot boundary in the cascade file), never
typed in: every kept feature ends at or before that boundary. Timestamps and
stage labels are stripped from the curated features so the prediction path
cannot see them even by accident.

Outputs:
  inputs/pre_t1_features.geojson  destroyed features at or before the cutoff
  inputs/waterways.geojson         mapped waterways (all reaches)
  inputs/target_reach.geojson      waterway pieces named by rules.json target
  inputs/extent.json               static observed-flood outline summary
  inputs/input_audit.json          source file -> sha256, filter, counts
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEMO = ROOT / "demo" / "nepal_cascade"
OUT = DEMO / "inputs"


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _m(geom) -> tuple:
    """Project lon/lat to local meters (latitude-corrected equirectangular)."""
    from shapely.ops import transform as _t

    lat0 = geom.centroid.y
    kx = 111320.0 * math.cos(math.radians(lat0))

    def fwd(x, y, z=None):
        return (x * kx, y * 110540.0)

    return _t(fwd, geom)


def main() -> int:
    from shapely.geometry import shape as _shape

    rules = json.loads((DEMO / "rules.json").read_text())
    target_prop = rules["cluster_rule"]["target_property"]
    target_value = rules["cluster_rule"]["target_value"]

    cascade_path = ROOT / "data" / "raw" / "temporal_data" / "osm_temporal_cascades.geojson"
    cascade = json.loads(cascade_path.read_text())
    feats = cascade.get("features", [])

    def end_of(f):
        return (f.get("properties") or {}).get("destruction_interval_end")

    ends = sorted({e for f in feats for e in [end_of(f)] if e})
    if not ends:
        print("no interval ends in cascade file", file=sys.stderr)
        return 1
    cutoff = ends[0]
    kept = [f for f in feats if (end_of(f) or "") <= cutoff]

    OUT.mkdir(parents=True, exist_ok=True)
    curated = []
    for f in kept:
        g = _shape(f["geometry"])
        if g.is_empty:
            continue
        p = f.get("properties") or {}
        curated.append({
            "type": "Feature",
            "properties": {"src_id": str(p.get("id") or p.get("way_id") or ""),
                           "feature_type": str(p.get("feature_type") or "")},
            "geometry": f["geometry"],
        })
    (OUT / "pre_t1_features.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": curated}) + "\n")

    ww_path = ROOT / "data" / "flood_nepal" / "waterways.geojson"
    waterways = json.loads(ww_path.read_text())
    (OUT / "waterways.geojson").write_text(json.dumps(waterways) + "\n")
    target = [f for f in waterways["features"]
              if ((f.get("properties") or {}).get(target_prop) or "") == target_value]
    (OUT / "target_reach.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": target}) + "\n")

    ext_path = ROOT / "data" / "flood_nepal" / "flood_extent.geojson"
    extent = json.loads(ext_path.read_text())
    egeom = _shape(extent["features"][0]["geometry"])
    proj = _m(egeom)
    (OUT / "extent.json").write_text(json.dumps({
        "centroid": list(egeom.centroid.coords[0]),
        "bbox": list(egeom.bounds),
        "area_m2": float(proj.area),
        "note": "static observed outline of the first flood; carries no time signal",
    }, indent=1) + "\n")

    audit = {
        "as_of_label": rules["cutoff"]["label"],
        "cutoff_derivation": "earliest destruction_interval_end found in the cascade file",
        "cutoff_value": cutoff,
        "later_boundaries_ignored": ends[1:],
        "sources": {str(cascade_path.relative_to(ROOT)): _sha(cascade_path),
                    str(ww_path.relative_to(ROOT)): _sha(ww_path),
                    str(ext_path.relative_to(ROOT)): _sha(ext_path)},
        "filter": "kept features with destruction_interval_end <= cutoff; stripped all timestamps and stage labels",
        "counts": {"cascade_total": len(feats), "kept_pre_cutoff": len(curated),
                   "waterways": len(waterways["features"]),
                   "target_reach_pieces": len(target)},
    }
    (OUT / "input_audit.json").write_text(json.dumps(audit, indent=1) + "\n")
    print(f"curated {len(curated)} pre-cutoff features "
          f"(cutoff {cutoff}); target pieces: {len(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
