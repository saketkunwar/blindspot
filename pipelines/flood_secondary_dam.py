#!/usr/bin/env python3
"""T-3.2 Flood pipeline: Act 1 snapshots, Act 2 blind-spot bands, Act 3 dipole.

Exit 0 on success, including when optional Act 3 inputs are missing (reported
as `missing_input`). Non-zero on incomplete config or manifest failure. Reads
all data from --data-dir.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

from shapely.ops import unary_union

from engine import gap_auditor as ga
from engine.qstr_core import snapshot_pair
from engine.schemas import DetectorVerdict, Hypothesis, load_preregistered
from pipelines.loader import ManifestError, load_manifest, read_geojson_features, verify_path

LAYER_FILES = (("bridges", "bridges.geojson"), ("hydropowers", "hydropowers.geojson"),
               ("helipads", "helipads.geojson"))
OPTIONAL = ("barrier_lake.geojson", "sar_anomaly_union.geojson")


def _m2(geom) -> float:
    """Planar area in m2 (latitude-corrected equirectangular projection)."""
    from shapely.ops import transform as _t

    lat0 = geom.centroid.y
    kx = 111320.0 * math.cos(math.radians(lat0))

    def fwd(x, y, z=None):
        return (x * kx, y * 110540.0)

    return float(_t(fwd, geom).area)


def _mbr_disjoint(rect_a, rect_b) -> bool:
    ax, ay = rect_a.bounds, rect_b.bounds
    return ax[2] < ay[0] or ay[2] < ax[0] or ax[3] < ay[1] or ay[3] < ax[1]


def _maybe_cached(out: pathlib.Path, inputs: list, use_cache: bool) -> bool:
    if not (use_cache and out.exists()):
        return False
    try:
        prior = json.loads(out.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return prior.get("inputs") == inputs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="config/preregistered.yaml")
    ap.add_argument("--fast-cache", action="store_true")
    a = ap.parse_args(argv)

    data = pathlib.Path(a.data_dir)
    try:
        cfg = load_preregistered(a.config)
    except Exception as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(data)
    except ManifestError as e:
        print(f"manifest error: {e}", file=sys.stderr)
        return 1

    flood_dir = data / "flood_nepal"
    inputs: list[dict] = []

    def need(name: str) -> pathlib.Path:
        p = flood_dir / name
        if not p.exists():
            print(f"missing required input: flood_nepal/{name}", file=sys.stderr)
            raise SystemExit(1)
        try:
            inputs.append(verify_path(p, manifest, data))
        except ManifestError as e:
            print(f"manifest error: {e}", file=sys.stderr)
            raise SystemExit(1)
        return p

    try:
        extent_p = need("flood_extent.geojson")
        layer_ps = [(layer, need(fname)) for layer, fname in LAYER_FILES]
        waterways_p = need("waterways.geojson")
        before_p = need("destroyed_before.geojson")
        after_p = need("destroyed_after.geojson")
    except SystemExit as e:
        return int(e.code or 1)
    if _maybe_cached(pathlib.Path(a.out), inputs, a.fast_cache):
        print("cached: inputs unchanged")
        return 0

    ingest = cfg["tolerance"]["ingest_deg"]
    extent = read_geojson_features(extent_p, ingest)[0][1]

    # ---- Act 1
    features = []
    for layer, path in layer_ps:
        for idx, (_, geom) in enumerate(read_geojson_features(path, ingest)):
            fwd, inv = snapshot_pair(geom, extent, cfg)
            mbr_sep = _mbr_disjoint(geom, extent)
            features.append({
                "id": f"{layer}:{idx}",
                "layer": layer,
                "fwd": fwd,
                "inv": inv,
                "split_alert": (fwd["rcc8"]["relation"] == "DC") != mbr_sep,
            })

    # ---- Act 2
    waterways = [g for _, g in read_geojson_features(waterways_p, ingest)]
    band_union = unary_union(waterways)
    bands = ga.blind_spot_bands(band_union, float(cfg["flood"]["blind_window_hours"]),
                                float(cfg["flood"]["v_max_m_per_hr"]))
    from shapely.geometry import shape as _shape
    may_be = _shape(bands["may_be"])
    layer_geoms = {layer: [g for _, g in read_geojson_features(path, ingest)]
                   for layer, path in layer_ps}
    assets = [(f["id"], f["layer"], layer_geoms[f["layer"]][int(f["id"].split(":")[1])])
              for f in features]
    in_may, out_may = ga.classify_assets(may_be, assets)
    from engine import fhz as _fhz
    zones = _fhz.split_zones(bands["must_be"])
    asset_union = unary_union([a for _, _, a in assets])
    fhz_report = _fhz.validate_zones(
        zones, extent, asset_union, (extent.centroid.x, extent.centroid.y))

    # ---- Act 3
    missing = [n for n in OPTIONAL if not (flood_dir / n).exists()]
    before = read_geojson_features(before_p, ingest)
    after = read_geojson_features(after_p, ingest)
    flat = extent.centroid.y

    def zone_area(feats) -> tuple[float, float]:
        up = down = 0.0
        for _, geom in feats:
            if geom.intersects(extent):
                continue
            a = _m2(geom)
            if geom.centroid.y >= flat:
                up += a
            else:
                down += a
        return up, down

    up0, down0 = zone_area(before)
    up1, down1 = zone_area(after)
    zone_evidence = {"up_t0": up0, "down_t0": down0, "up_t1": up1, "down_t1": down1,
                     "destroyed_before": len(before), "destroyed_after": len(after)}
    if missing:
        detector_a = DetectorVerdict(
            triggered=False,
            reason=f"missing_input: {', '.join('flood_nepal/' + m for m in missing)}; "
                   "no impoundment geometry invented.",
            hypotheses=[Hypothesis(id="free_drainage", supports=[], refutes=[], status="OPEN"),
                        Hypothesis(id="impoundment", supports=[], refutes=[], status="OPEN")],
            evidence=[{"missing": missing, **zone_evidence}],
        )
        union_snap = None
        status = "missing_input"
    else:
        for n in OPTIONAL:
            inputs.append(verify_path(flood_dir / n, manifest, data))
        lake = unary_union([g for _, g in read_geojson_features(flood_dir / OPTIONAL[0], ingest)])
        union = unary_union([g for _, g in read_geojson_features(flood_dir / OPTIONAL[1], ingest)])
        fwd_u, inv_u = snapshot_pair(lake, union, cfg)
        union_snap = {"fwd": fwd_u, "inv": inv_u}
        rivals = ga.predict_a_rivals(up0, down0)
        detector_a = ga.judge_detector_a(rivals, up0, down0, up1, down1)
        status = "ok"

    result = {
        "scenario": "flood_nepal",
        "inputs": inputs,
        "act1": {"features": features},
        "act2": {
            "blind_window_hours": float(cfg["flood"]["blind_window_hours"]),
            "must_be": bands["must_be"],
            "may_be": bands["may_be"],
            "assets_in_may_be": sorted(in_may, key=lambda x: x["id"]),
            "fhz_zones": {"n_zones": fhz_report["n_zones"],
                          "informative_total": fhz_report["informative_total"]},
            "assets_outside": sorted(out_may, key=lambda x: x["id"]),
        },
        "act3": {
            "status": status,
            "missing": missing,
            "impoundment_vs_union": union_snap,
            "detector_a": detector_a.model_dump(),
        },
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(f"wrote {out} act1={len(features)} act2_in={len(in_may)} act3={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
