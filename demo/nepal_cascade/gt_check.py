#!/usr/bin/env python3
"""Formal ground-truth check for the Nepal demo. READ-ONLY and POST-FREEZE.

Compares the FROZEN prediction (output/brief.json, never modified here)
against ground truth the prediction could never see: the T1->T2 destruction
delta from the raw cascade file plus the Sep-7 SAR barrier-lake log. No
re-tuning is possible from this script: it takes no weights, writes no
rules, and touches only output/gt_check.json.

GT window and groups are derived from the data (sorted interval ends and
stage groupings), not typed in. Geometry uses the same helpers as the
prediction so the comparison is like-for-like.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DEMO = ROOT / "demo" / "nepal_cascade"


def _m(geom):
    from shapely.ops import transform as _t

    lat0 = geom.centroid.y
    kx = 111320.0 * math.cos(math.radians(lat0))

    def fwd(x, y, z=None):
        return (x * kx, y * 110540.0)

    return _t(fwd, geom)


def main() -> int:
    from shapely.geometry import shape as _shape
    from shapely.ops import unary_union

    brief = json.loads((DEMO / "output" / "brief.json").read_text())
    rules = json.loads((DEMO / "rules.json").read_text())
    frozen_top = brief["mechanisms"][0]["id"]

    cascade = json.loads((ROOT / "data" / "raw" / "temporal_data"
                          / "osm_temporal_cascades.geojson").read_text())
    feats = cascade["features"]
    ends = sorted({(f.get("properties") or {}).get("destruction_interval_end")
                   for f in feats} - {None})
    cutoff = ends[0]
    stages: dict[str, set[str]] = {}
    for f in feats:
        p = f.get("properties") or {}
        stages.setdefault(str(p.get("destruction_stage")), set()).add(
            p.get("destruction_interval_end"))
    gt_stage = min((s for s in stages if ends[0] not in stages[s]),
                   key=lambda s: min(e for e in stages[s] if e))
    gt = [f for f in feats
          if str((f.get("properties") or {}).get("destruction_stage")) == gt_stage]
    gt_max_end = max(stages[gt_stage])

    extent = json.loads((DEMO / "inputs" / "extent.json").read_text())
    lat0 = float(extent["centroid"][1])
    waterways = json.loads((DEMO / "inputs" / "waterways.geojson").read_text())
    target = json.loads((DEMO / "inputs" / "target_reach.geojson").read_text())
    wunion = unary_union([_m(_shape(f["geometry"])) for f in waterways["features"]
                          if f.get("geometry")])
    tunion = unary_union([_m(_shape(f["geometry"])) for f in target["features"]
                          if f.get("geometry")])
    adj = float(rules.get("channel_adjacent_m", 250))
    cl = rules["cluster_rule"]

    proj = [_m(_shape(f["geometry"])) for f in gt if f.get("geometry")]
    n = len(proj)
    # upstream = north of the extent centroid latitude (same neck rule)
    up = sum(1 for f in gt
             if _shape(f["geometry"]).centroid.y > lat0) if gt else 0
    near_chan = sum(1 for g in proj if g.distance(wunion) <= adj)
    near_target = sum(1 for g in proj
                      if tunion is not None and not tunion.is_empty
                      and g.distance(tunion) <= float(cl["max_distance_m"]))
    sig = {
        "gt_window": f"({cutoff}, {gt_max_end}]",
        "gt_newly_destroyed": n,
        "gt_upstream_share": round(up / n, 4) if n else 0.0,
        "gt_channel_adjacent_share": round(near_chan / n, 4) if n else 0.0,
        "gt_near_target": near_target,
        "gt_cluster_hit": bool(near_target >= int(cl["min_features"])),
    }

    sar = json.loads((ROOT / "data" / "raw" / "flood_data_processed"
                      / "barrier_lake_area_log.json").read_text())
    lakes = [e for e in sar
             if cutoff < str(e.get("timestamp", "")) <= gt_max_end
             and float(e.get("area_km2", 0) or 0) > 0]
    sig["sar_lake_between_snapshots"] = bool(lakes)
    sig["sar_max_area_km2"] = max((float(e["area_km2"]) for e in lakes), default=0.0)

    burst_like = (sig["gt_upstream_share"] > 0.5
                  and sig["gt_channel_adjacent_share"] > 0.5
                  and (sig["gt_cluster_hit"] or sig["sar_lake_between_snapshots"]))
    match = bool(burst_like and frozen_top == "impoundment_then_burst")
    result = {
        "frozen_top_mechanism": frozen_top,
        "frozen_top_support": brief["mechanisms"][0]["probability"],
        "frozen_ranking": [m["id"] for m in brief["mechanisms"]],
        "gt_signature": sig,
        "true_outcome_rank": 1 if match else None,
        "verdict": ("MATCH: the frozen top story (impoundment_then_burst) is "
                    "consistent with the quarantined T1->T2 delta and SAR log"
                    if match else
                    "MISMATCH: the frozen top story is not supported by the "
                    "quarantined ground truth"),
        "discipline": "read-only; no weights, rules, or brief bytes were touched",
    }
    out = DEMO / "output" / "gt_check.json"
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(result["verdict"])
    print(json.dumps(sig, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
