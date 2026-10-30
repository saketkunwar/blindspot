#!/usr/bin/env python3
"""Rolling-origin fire episodes for BlindSpot tiered memory (M0).

Slides cutoffs within each stored FIRMS fire scene. For every cutoff with at
least ``minimum_history_days`` distinct burn days on/before it, the script:

1. builds the prediction slice — detections with day <= cutoff ONLY (the
   same ``day > cutoff: continue`` comparison as demo/fire_study/curate.py),
2. recomputes grid cells and the study-box extent from that slice alone, so
   no post-cutoff byte (counts, hot tags, bounding boxes) leaks in,
3. runs the FROZEN study ranking — engine.ledger.compute_ledger_from_spec +
   engine.ledger.score_mechanisms over demo/fire_study/rules.json with the
   closed engine.facts op set (this script invents no scoring),
4. labels the outcome with the preregistered memory rule
   (config/preregistered_memory.yaml) from detections strictly after the
   cutoff inside the look-ahead window.

Episodes and outcomes are appended to a SQLite store (insert-only; rerunning
an episode id fails instead of overwriting). Episodes whose look-ahead
window runs past the observed scene span are stored as "unlabelable" and
kept in the census.

Usage:
  python scripts/backtest_episodes.py --scene data/fire_kalimantan/firms_kalimantan_c.json
      --rules demo/fire_study/rules.json --memory-config config/preregistered_memory.yaml
      --db results/memory_episodes.sqlite3 [--census-out results/memory_census.json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.ledger import compute_ledger_from_spec, score_mechanisms  # noqa: E402
from pipelines.loader import load_manifest, parse_firms_detections, verify_path  # noqa: E402
from store import db as store  # noqa: E402

DAY = _dt.timedelta(days=1)


def _read_yaml(path: pathlib.Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text())


def _scene_tag(obj, path: pathlib.Path) -> str:
    if isinstance(obj, dict) and isinstance(obj.get("tag"), str) and obj["tag"]:
        return obj["tag"]
    return path.stem


def _verify_scene(scene: pathlib.Path, data_dir: pathlib.Path) -> str:
    manifest = load_manifest(data_dir)
    info = verify_path(scene.resolve(), manifest, data_dir.resolve())
    return info["sha256"]


def _build_roles(dets_pre: list, grid_deg: float, noise_floor: int) -> tuple[dict, int]:
    """Roles for the frozen ledger from the pre-cutoff slice only.

    Mirrors demo/fire_study/curate.py: sorted traversal, floor grid, hot at
    >= noise floor, extent from the slice bounding box. Returns (roles,
    cell_count).
    """
    ordered = sorted(dets_pre)  # (day, lon, lat); deterministic
    det_feats = [
        {"type": "Feature",
         "properties": {"src_id": f"det-{i:06d}", "day": day},
         "geometry": {"type": "Point", "coordinates": [lon, lat]}}
        for i, (day, lon, lat) in enumerate(ordered)
    ]
    cells: dict = {}
    for day, lon, lat in ordered:
        ox = math.floor(lon / grid_deg) * grid_deg
        oy = math.floor(lat / grid_deg) * grid_deg
        key = f"{ox:.1f},{oy:.1f}"
        cell = cells.setdefault(key, {"origin": [ox, oy], "counts": {}})
        cell["counts"][day] = cell["counts"].get(day, 0) + 1
    cell_feats = []
    for key in sorted(cells):
        ox, oy = cells[key]["origin"]
        counts = cells[key]["counts"]
        total = sum(counts.values())
        cell_feats.append({
            "type": "Feature",
            "properties": {"cell_id": key, "days": sorted(counts),
                           "counts": counts, "total": total,
                           "hot": total >= noise_floor},
            "geometry": {"type": "Polygon", "coordinates": [[
                [ox, oy], [ox + grid_deg, oy], [ox + grid_deg, oy + grid_deg],
                [ox, oy + grid_deg], [ox, oy]]]}})
    lons = [lon for _, lon, _ in ordered]
    lats = [lat for _, _, lat in ordered]
    roles = {
        "detections": {"type": "FeatureCollection", "features": det_feats},
        "cells": {"type": "FeatureCollection", "features": cell_feats},
        "boundary": {"bbox": [min(lons), min(lats), max(lons), max(lats)],
                     "note": "study box from pre-cutoff slice; carries no time signal"},
    }
    return roles, len(cell_feats)


def run_scene(scene: pathlib.Path, rules: dict, mem: dict, con,
              stats: dict) -> None:
    obj = json.loads(scene.read_text())
    tag = _scene_tag(obj, scene)
    dets = parse_firms_detections(obj)
    if not dets:
        print(f"scene {tag}: no parseable detections, skipped")
        stats["scenes_skipped"] += 1
        return
    digest = hashlib.sha256(scene.read_bytes()).hexdigest()
    days = sorted({d for d, _, _ in dets})
    lo = (mem.get("curation_mirror") or {}).get("grid_cell_deg", 0.5)
    floor = (mem.get("curation_mirror") or {}).get("noise_floor_detections", 3)
    min_hist = int(mem["minimum_history_days"])
    look = int(mem["look_ahead_days"])
    rule_id = str(mem.get("rule_id", "memory-v1"))
    restart_min = int((mem.get("outcome") or {}).get("restart_min_detections", 3))
    unlab = str(mem.get("unlabelable_label", "unlabelable"))
    max_day = days[-1]

    for cutoff in days:
        pre = [(d, lo_, la) for d, lo_, la in dets if d <= cutoff]
        post = [(d, lo_, la) for d, lo_, la in dets if d > cutoff]
        # Fail-closed leakage guard: the prediction slice holds no future day.
        assert all(d <= cutoff for d, _, _ in pre), f"leak: pre past {cutoff}"
        assert all(d > cutoff for d, _, _ in post), "window mis-split"
        days_pre = sorted({d for d, _, _ in pre})
        if len(days_pre) < min_hist:
            print(f"episode {tag}@{cutoff}: skipped "
                  f"({len(days_pre)} history days < {min_hist})")
            stats["skipped_thin_history"] += 1
            continue
        roles, n_cells = _build_roles(pre, lo, floor)
        ledger = compute_ledger_from_spec(rules, roles)
        ranking = score_mechanisms(rules, ledger)
        top = ranking[0]["id"]
        ep_id = f"{tag}@{cutoff}"
        store.add_episode(con, ep_id, tag, digest, cutoff, len(pre),
                          days_pre, n_cells, ledger["facts"], ranking, top)
        c_date = _dt.date.fromisoformat(cutoff)
        w_start = (c_date + DAY).isoformat()
        w_end = (c_date + look * DAY).isoformat()
        in_window = [d for d, _, _ in post if w_start <= d <= w_end]
        if max_day < w_end:
            label, n_post = unlab, len(in_window)
        else:
            n_post = len(in_window)
            out = mem.get("outcome") or {}
            label = (str(out.get("positive_label", "restart"))
                     if n_post >= restart_min
                     else str(out.get("negative_label", "quiet")))
        store.add_outcome(con, ep_id, rule_id, look, w_start, w_end,
                          n_post, label)
        stats["episodes"] += 1
        if label == unlab:
            stats["unlabelable"] += 1
        print(f"episode {ep_id}: n_pre={len(pre)} cells={n_cells} "
              f"top={top} outcome={label} (n_post={n_post})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", action="append", default=[],
                    help="FIRMS scene file (repeatable)")
    ap.add_argument("--all-scenes", action="store_true",
                    help="use every data/fire_kalimantan/*.json scene")
    ap.add_argument("--rules", default=str(ROOT / "demo/fire_study/rules.json"))
    ap.add_argument("--memory-config",
                    default=str(ROOT / "config/preregistered_memory.yaml"))
    ap.add_argument("--db", default="results/memory_episodes.sqlite3")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--no-manifest-check", action="store_true",
                    help="skip MANIFEST verification (tests only)")
    ap.add_argument("--census-out", default=None)
    a = ap.parse_args(argv)

    scenes = list(a.scene)
    if a.all_scenes:
        scenes += sorted(str(p) for p in
                         (ROOT / "data/fire_kalimantan").glob("*.json"))
    if not scenes:
        scenes = [str(ROOT / "data/fire_kalimantan/firms_kalimantan_c.json")]
    rules = json.loads(pathlib.Path(a.rules).read_text())
    mem = _read_yaml(pathlib.Path(a.memory_config))
    for key in ("look_ahead_days", "minimum_history_days", "outcome"):
        if mem.get(key) is None:
            print(f"memory config incomplete: {key} is null; refusing to run")
            return 2

    data_dir = pathlib.Path(a.data_dir)
    db_path = pathlib.Path(a.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = store.connect(db_path)
    stats = {"episodes": 0, "unlabelable": 0, "skipped_thin_history": 0,
             "scenes_skipped": 0}
    try:
        for s in scenes:
            sp = pathlib.Path(s)
            if not a.no_manifest_check:
                try:
                    _verify_scene(sp, data_dir)
                except Exception as e:
                    print(f"refusing scene {s}: {e}")
                    return 2
            run_scene(sp, rules, mem, con, stats)
        con.commit()
    finally:
        con.close()

    con = store.connect(db_path)
    try:
        rows = store.census(con)
    finally:
        con.close()
    print(f"\ncensus: {len(rows)} episodes "
          f"({stats['unlabelable']} unlabelable, "
          f"{stats['skipped_thin_history']} skipped for thin history)")
    print("| episode | cutoff | n_pre | cells | top | window | n_post | label |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        win = (f"{r['window_start']}..{r['window_end']}"
               if r["window_start"] else "-")
        print(f"| {r['episode_id']} | {r['cutoff']} | {r['n_pre']} | "
              f"{r['cells_pre']} | {r['top_mechanism']} | {win} | "
              f"{r['n_post']} | {r['label']} |")
    if a.census_out:
        out = pathlib.Path(a.census_out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"config": "config/preregistered_memory.yaml",
                                   "rule_id": mem.get("rule_id"),
                                   "episodes": rows, "stats": stats},
                                  indent=1, sort_keys=True) + "\n")
        print(f"census written to {out}")
    print(f"db: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
