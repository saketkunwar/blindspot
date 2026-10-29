#!/usr/bin/env python3
"""Curate the Kalimantan fire study inputs (Demo 2, P0 Step 6).

Reads ONLY data/fire_kalimantan/firms_kalimantan_c.json (never data/raw).
Writes demo/fire_study/inputs/: detections (points, day retained — spread
over days IS the phenomenon here, unlike the single-snapshot flood; the
card redacts dates from prompt text and the prompt audit enforces it),
cells (0.5-degree floor grid, the frozen config value), timeline (daily
phases), extent, and the input audit. Deterministic: sorted traversal,
fixed key order, no wall-clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CUTOFF = "2026-09-20"
GRID_DEG = 0.5  # frozen config grid.cell_deg


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "demo" / "fire_study" / "inputs"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    src = ROOT / "data" / "fire_kalimantan" / "firms_kalimantan_c.json"
    obj = json.loads(src.read_text())
    recs = []
    for i, rec in enumerate(obj.get("detections", [])):
        payload = rec.get("payload", {}) if isinstance(rec.get("payload"), dict) else {}
        day = str(payload.get("acq_date", ""))[:10]
        try:
            lon, lat = float(rec["lon"]), float(rec["lat"])
        except (KeyError, TypeError, ValueError):
            continue
        if not day or day > CUTOFF:
            continue
        recs.append({"id": f"det-{i:06d}", "lon": lon, "lat": lat, "day": day})
    recs.sort(key=lambda r: (r["day"], r["lon"], r["lat"]))
    for j, r in enumerate(recs):
        r["id"] = f"det-{j:06d}"

    detections = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"src_id": r["id"], "day": r["day"]},
         "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]}}
        for r in recs]}
    (out / "detections.geojson").write_text(json.dumps(detections) + "\n")

    cells: dict = {}
    for r in recs:
        ox = math.floor(r["lon"] / GRID_DEG) * GRID_DEG
        oy = math.floor(r["lat"] / GRID_DEG) * GRID_DEG
        key = f"{ox:.1f},{oy:.1f}"
        cell = cells.setdefault(key, {"origin": [ox, oy], "counts": {}})
        cell["counts"][r["day"]] = cell["counts"].get(r["day"], 0) + 1
    cell_feats = []
    for key in sorted(cells):
        ox, oy = cells[key]["origin"]
        counts = cells[key]["counts"]
        total = sum(counts.values())
        cell_feats.append({
            "type": "Feature",
            # hot = at least the frozen FIRMS noise floor (3 detections);
            # a curation-time tag so closed ops can scope by concentration.
            "properties": {"cell_id": key, "days": sorted(counts),
                           "counts": counts, "total": total,
                           "hot": total >= 3},
            "geometry": {"type": "Polygon", "coordinates": [[
                [ox, oy], [ox + GRID_DEG, oy], [ox + GRID_DEG, oy + GRID_DEG],
                [ox, oy + GRID_DEG], [ox, oy]]]}})
    (out / "cells.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": cell_feats}) + "\n")

    days = sorted({r["day"] for r in recs})
    timeline = {"phases": [
        {"id": f"day-{d}", "start": f"{d}T00:00:00Z", "end": f"{d}T23:59:59Z"}
        for d in days]}
    (out / "timeline.json").write_text(json.dumps(timeline, indent=1) + "\n")

    lons = [r["lon"] for r in recs]
    lats = [r["lat"] for r in recs]
    extent = {
        "centroid": [sum(lons) / len(lons), sum(lats) / len(lats)],
        "bbox": [min(lons), min(lats), max(lons), max(lats)],
        "note": "study box from pre-cutoff detections; carries no time signal",
    }
    (out / "extent.json").write_text(json.dumps(extent, indent=1) + "\n")

    audit = {
        "as_of_label": f"pre-{CUTOFF}",
        "cutoff_derivation": "max evidence date in the FIRMS file",
        "cutoff_value": f"{CUTOFF}T23:59:59Z",
        "sources": {str(src.relative_to(ROOT)): sha(src)},
        "filter": ("kept detections on or before cutoff; day labels retained "
                   "because multi-day spread is the phenomenon (unlike the "
                   "single-snapshot flood); card redacts dates from prompts"),
        "counts": {"detections": len(recs), "days": len(days),
                   "cells": len(cell_feats)},
    }
    (out / "input_audit.json").write_text(json.dumps(audit, indent=1) + "\n")
    print(f"curated {len(recs)} detections, {len(days)} days, "
          f"{len(cell_feats)} cells -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
