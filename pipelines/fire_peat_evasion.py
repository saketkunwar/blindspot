#!/usr/bin/env python3
"""T-3.3 Fire pipeline: per-cell footprints, continuity, timeline, claim, Detector B.

Exit 0 on success. Non-zero on incomplete config or manifest failure. Reads
all data from --data-dir. Deterministic under input point reordering.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from collections import defaultdict

from shapely.geometry import Point, box
from shapely.ops import unary_union

from engine import gap_auditor as ga
from engine.qstr_core import allen, rcc8
from engine.schemas import load_preregistered
from pipelines.loader import ManifestError, firms_tag, load_manifest, parse_firms_detections, verify_path

_M_PER_DEG_LAT = 110540.0
_M_PER_DEG_LON = 111320.0


def _maybe_cached(out: pathlib.Path, inputs: list, use_cache: bool) -> bool:
    if not (use_cache and out.exists()):
        return False
    try:
        prior = json.loads(out.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return prior.get("inputs") == inputs


def _cell_origin(lon: float, lat: float, deg: float) -> tuple[float, float]:
    return (math.floor(lon / deg) * deg, math.floor(lat / deg) * deg)


def _pick_scenario_file(fire_dir: pathlib.Path, site: str, timeline_days: set[str]):
    """Data-driven scenario selection: tag matching the timeline site, else the
    file with most detections inside the timeline window, else most overall."""
    scored = []
    for path in sorted(fire_dir.glob("*.json")):
        try:
            obj = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        try:
            dets = parse_firms_detections(obj)
        except ManifestError:
            continue
        tag = firms_tag(obj).lower()
        in_window = sum(1 for d, _, _ in dets if d in timeline_days)
        scored.append((site.lower() in tag, in_window, len(dets), path))
    if not scored:
        raise ManifestError(f"no readable FIRMS files in {fire_dir}")
    scored.sort(key=lambda s: (s[0], s[1], s[2]))
    return scored[-1][3]


def _project(lon: float, lat: float, lat0: float) -> tuple[float, float]:
    return (lon * _M_PER_DEG_LON * math.cos(math.radians(lat0)), lat * _M_PER_DEG_LAT)


def _clusters(points_m: list[tuple[float, float]], link_m: float) -> list[list[int]]:
    """Union-find over a spatial hash; links closer than link_m (buffer touch)."""
    cell = max(link_m, 1.0)
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (x, y) in enumerate(points_m):
        buckets[(int(x // cell), int(y // cell))].append(i)
    parent = list(range(len(points_m)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (bx, by), members in buckets.items():
        near = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near += buckets.get((bx + dx, by + dy), [])
        for i in members:
            xi, yi = points_m[i]
            for j in near:
                if j <= i:
                    continue
                xj, yj = points_m[j]
                if (xi - xj) ** 2 + (yi - yj) ** 2 < link_m * link_m:
                    union(i, j)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(points_m)):
        groups[find(i)].append(i)
    return list(groups.values())


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

    inputs: list[dict] = []

    def need(path: pathlib.Path) -> pathlib.Path:
        try:
            inputs.append(verify_path(path, manifest, data))
        except ManifestError as e:
            print(f"manifest error: {e}", file=sys.stderr)
            raise SystemExit(1)
        return path

    fire_dir = data / "fire_kalimantan"
    timeline_p = data / "synthetic" / "operator_timeline.json"
    try:
        need(timeline_p)
        timeline = json.loads(timeline_p.read_text())
        window = set()
        for iv in timeline["phases"] + [timeline["claim"]]:
            window.add(iv["start"])
            window.add(iv["end"])
        scen_p = _pick_scenario_file(fire_dir, str(timeline.get("site", "")), window)
        need(scen_p)
    except SystemExit as e:
        return int(e.code or 1)
    if _maybe_cached(pathlib.Path(a.out), inputs, a.fast_cache):
        print("cached: inputs unchanged")
        return 0

    deg = float(cfg["grid"]["cell_deg"])
    min_det = int(cfg["fire"]["min_detections"])
    buf_m = float(cfg["fire"]["footprint_buffer_m"])
    detections = parse_firms_detections(json.loads(scen_p.read_text()))

    by_cell_day: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for day, lon, lat in detections:
        ox, oy = _cell_origin(lon, lat, deg)
        by_cell_day[f"{ox:.1f},{oy:.1f}"][day].append((lon, lat))
    dates = sorted({d for d, _, _ in detections})
    if detections:
        lat0 = sum(lat for _, _, lat in detections) / len(detections)
    else:
        lat0 = 0.0

    cells = []
    for cid in sorted(by_cell_day):
        ox, oy = (float(v) for v in cid.split(","))
        cx0, cy0 = _project(ox, oy, lat0)
        cx1, cy1 = _project(ox + deg, oy + deg, lat0)
        cell_poly = box(min(cx0, cx1), min(cy0, cy1), max(cx0, cx1), max(cy0, cy1))
        counts, rcc8s, continuity = {}, {}, []
        for day in dates:
            pts = by_cell_day[cid].get(day, [])
            counts[day] = len(pts)
            if pts:
                pts_m = [_project(lon, lat, lat0) for lon, lat in pts]
                unions = []
                for members in _clusters(pts_m, 2 * buf_m):
                    if len(members) < min_det:
                        continue
                    blob = unary_union([Point(p).buffer(buf_m)
                                        for p in (pts_m[m] for m in members)])
                    if blob.intersects(cell_poly):
                        unions.append(blob)
                rcc8s[day] = rcc8(unary_union(unions), cell_poly) if unions else "DC"
            else:
                rcc8s[day] = "DC"
        for d0, d1 in zip(dates, dates[1:]):
            tr = ga.check_continuity(cid, d0, d1, rcc8s[d0], rcc8s[d1])
            continuity.append({"from_date": d0, "to_date": d1,
                               "violation": tr.kind == "DISCONTINUOUS_JUMP",
                               "missing_intermediates": tr.missing_intermediates})
        cells.append({"id": cid, "origin": [ox, oy], "counts": counts,
                      "rcc8": rcc8s, "continuity": continuity})

    ids = [p["id"] for p in timeline["phases"]] + [timeline["claim"]["id"]]
    bounds = {p["id"]: (p["start"], p["end"]) for p in timeline["phases"] + [timeline["claim"]]}
    timeline_relations = [
        {"a": x, "b": y, "relation": allen(bounds[x][0], bounds[x][1], bounds[y][0], bounds[y][1])}
        for x in ids for y in ids if x != y
    ]
    claim = timeline["claim"]
    overlap_days = sorted({d for d, _, _ in detections if d >= claim["start"] and d < claim["end"]})
    claims = [{
        "id": claim["id"],
        "text": claim.get("text", ""),
        "start": claim["start"],
        "end": claim["end"],
        "verdict": "falsified" if overlap_days else "not_falsified",
        "evidence": [{"overlap_days": overlap_days[:10], "n_overlap_days": len(overlap_days)}],
    }]
    detector_b = ga.detector_b([(d, f"{_cell_origin(lon, lat, deg)[0]:.1f},{_cell_origin(lon, lat, deg)[1]:.1f}")
                                for d, lon, lat in detections], claim, cfg)

    result = {
        "scenario": "fire_kalimantan",
        "inputs": inputs,
        "grid_deg": deg,
        "dates": dates,
        "cells": cells,
        "timeline_relations": timeline_relations,
        "claims": claims,
        "detector_b": detector_b.model_dump(),
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(f"wrote {out} cells={len(cells)} dates={dates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
