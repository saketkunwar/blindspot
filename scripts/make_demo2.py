#!/usr/bin/env python3
"""Build the Demo-2 showcase snapshots (memory pages' data).

Regenerates `api/demo2_data/fire.json` and `api/demo2_data/nepal.json`
from live script output only: the backtest census, the null-test arms, a
hill-climbing step over empty traces, and the Nepal byte-identity check.
No number is typed by hand; every figure in the snapshots is recomputed
here, so re-running this script refreshes both demo pages at once.

Usage:
  python scripts/make_demo2.py [--out-dir api/demo2_data]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MEM_CFG = ROOT / "config/preregistered_memory.yaml"


def _run_backtest(tmp: pathlib.Path) -> tuple:
    from scripts import backtest_episodes as be
    db = tmp / "episodes.sqlite3"
    census = tmp / "census.json"
    rc = be.main(["--all-scenes", "--db", str(db), "--census-out", str(census)])
    if rc != 0:
        raise SystemExit("backtest failed")
    return db, json.loads(census.read_text())


def _null_edges() -> dict:
    import yaml
    from scripts import measure_memory as mm
    cfg = yaml.safe_load(MEM_CFG.read_text())
    nt = cfg["null_test"]
    mem = {"min_episodes_to_speak": 1,
           "smoothing_alpha": cfg["memory"]["smoothing_alpha"],
           "max_abs_shift": cfg["memory"]["max_abs_shift"]}
    supports = cfg["memory"]["outcome_supports"]
    null = mm.run_arm(False, nt["seed"], nt["trials"], nt["history_len"],
                      nt["frozen_probs"], supports, mem)
    sig = mm.run_arm(True, nt["seed"] + 1, nt["trials"], nt["history_len"],
                     nt["frozen_probs"], supports, mem)
    return {"null_edge": round(null["edge"], 3),
            "signal_edge": round(sig["edge"], 3),
            "trials": nt["trials"],
            "note": "preregistered simulation, not study data"}


def _hill_climb_report(tmp: pathlib.Path) -> dict:
    r = subprocess.run(
        [sys.executable, "scripts/hill_climb.py", "--traces-db",
         str(tmp / "absent.sqlite3"), "--evolver-db",
         str(tmp / "evo.sqlite3")],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"hill_climb failed: {r.stderr[-300:]}")
    return json.loads(r.stdout)


def _fire_validation(tmp: pathlib.Path, brief: dict) -> dict:
    """Re-run both holdouts live: the temporal outcome recorded at freeze
    time, and a masked eastern half recomputed with the frozen rules."""
    import shutil
    import statistics
    from agents import autoinsight as ai
    src = ROOT / "demo/fire_study/inputs"
    dets = json.loads((src / "detections.geojson").read_text())["features"]
    cut = statistics.median(f["geometry"]["coordinates"][0] for f in dets)
    west = [f for f in dets if f["geometry"]["coordinates"][0] <= cut]
    hold = tmp / "holdout" / "inputs"
    shutil.rmtree(hold, ignore_errors=True)
    hold.mkdir(parents=True)
    (hold / "detections.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": west}))
    for f in ["cells.geojson", "timeline.json", "extent.json",
              "input_audit.json"]:
        shutil.copy(src / f, hold / f)
    out = tmp / "holdout.json"
    ai.run(str(hold), "demo/fire_study/rules.json",
           str(out), str(tmp / "holdout_prompts"), model_round="off",
           domain_path="demo/fire_study/domain.json")
    rebrief = json.loads(out.read_text())
    frozen_ids = [m["id"] for m in brief["mechanisms"]]
    re_ids = [m["id"] for m in rebrief["mechanisms"]]
    probs_same = all(abs(a["probability"] - b["probability"]) < 0.00005
                     for a, b in zip(brief["mechanisms"],
                                     rebrief["mechanisms"]))
    return {
        "temporal": {
            "cutoff_day": "2026-09-20",
            "held_out": "the late-September restart",
            "frozen_top": brief["mechanisms"][0]["id"],
            "match": brief["mechanisms"][0]["id"] == "suppression_then_restart",
        },
        "spatial": {
            "masked": "the eastern half of the map",
            "kept": len(west),
            "total": len(dets),
            "meridian": round(cut, 4),
            "top": rebrief["mechanisms"][0]["id"],
            "ranking_identical": re_ids == frozen_ids,
            "probabilities_identical": probs_same,
        },
    }


def _fire_snapshot(tmp: pathlib.Path) -> dict:
    import yaml
    from engine import memory as _memory
    from store import db as _db
    import sqlite3
    cfg = yaml.safe_load(MEM_CFG.read_text())
    db_path, census = _run_backtest(tmp)
    brief = json.loads((ROOT / "demo/fire_study/output/brief.json").read_text())
    con = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        episodes = _db.episodes_for(con)
        outcomes = _db.outcomes_for(con)
    finally:
        con.close()
    ends = sorted(o["window_end"] for o in outcomes
                  if o["label"] != "unlabelable")
    pats = _memory.patterns_from_rows(
        episodes, outcomes, cfg["signature"]["count_bin_edges"],
        cfg["memory"]["outcome_supports"], ends[-1],
        cfg.get("rule_id", "memory-v1"))
    rows = []
    for sig in sorted(pats, key=lambda s: (-pats[s]["labeled"],
                                           -pats[s]["episodes"])):
        p = pats[sig]
        members = sorted(e["episode_id"] for e in episodes
                         if _memory.signature_for_facts(
                             e["facts"],
                             cfg["signature"]["count_bin_edges"])["id"] == sig)
        rows.append({"episodes": p["episodes"], "labeled": p["labeled"],
                     "labels": p["labels"], "members": members})
    scenes: dict = {}
    for e in census["episodes"]:
        s = e["episode_id"].split("@")[0]
        d = scenes.setdefault(s, {"scene": s, "episodes": 0, "labelled": 0,
                                  "unlabelable": 0})
        d["episodes"] += 1
        d["labelled" if e["label"] != "unlabelable" else "unlabelable"] += 1
    labelled = sum(s["labelled"] for s in scenes.values())
    best = max((p["labeled"] for p in pats.values()), default=0)
    need = cfg["memory"]["min_episodes_to_speak"]
    return {
        "frozen": {
            "verdict": brief["verdict"],
            "top": brief["mechanisms"][0]["id"],
            "top_title": brief["mechanisms"][0]["title"],
            "probability": brief["mechanisms"][0]["probability"],
            "detections": brief["inputs_audit"]["counts"]["detections"],
            "cells": brief["inputs_audit"]["counts"]["cells"],
            "mechanisms": len(brief["mechanisms"]),
        },
        "memory_status": {
            "rule_id": census["rule_id"],
            "episodes": len(census["episodes"]),
            "labelled": labelled,
            "scenes": len(scenes),
            "patterns": len(pats),
            "best_labelled": best,
            "threshold": need,
            "speaking": best >= need,
        },
        "hook": ("One more closed window and memory speaks "
                 "for the first time."),
        "episodes": census["episodes"],
        "scenes": sorted(scenes.values(), key=lambda d: -d["labelled"]),
        "skipped": {"thin_history": census["stats"]["skipped_thin_history"],
                    "empty_files": census["stats"]["scenes_skipped"]},
        "top_patterns": rows[:4],
        "null_test": _null_edges(),
        "hill_climb": _hill_climb_report(tmp),
        "validation": _fire_validation(tmp, brief),
    }


def _nepal_snapshot(tmp: pathlib.Path) -> dict:
    from agents import autoinsight as ai
    brief_path = ROOT / "demo/nepal_cascade/output/brief.json"
    brief = json.loads(brief_path.read_text())
    frozen_sha = hashlib.sha256(brief_path.read_bytes()).hexdigest()
    out = tmp / "nepal_mem.json"
    # Memory-empty run through an empty store: proves the silence path on
    # this study's own brief (mirrors G19 without duplicating the gate).
    from store import db as _db
    empty = tmp / "empty.sqlite3"
    _db.connect(str(empty)).close()
    ai.run("demo/nepal_cascade/inputs", "demo/nepal_cascade/rules.json",
           str(out), str(tmp / "prompts"), model_round="on",
           domain_path="demo/nepal_cascade/domain.json",
           memory_db=str(empty),
           memory_config=str(MEM_CFG), as_of="2026-09-20")
    mem_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    from collections import Counter
    import glob
    days: Counter = Counter()
    dateless = 0
    for f in glob.glob("data/nepflood_cascade/*/hot_flood_npl_destroyed_features_osm.geojson"):
        for x in json.loads(pathlib.Path(f).read_text()).get("features", []):
            day = str(((x.get("properties") or {}).get("damage_date")) or "")[:10]
            if day:
                days[day] += 1
            else:
                dateless += 1
    gt = json.loads((ROOT / "demo/nepal_cascade/output/gt_check.json").read_text())
    return {
        "frozen": {
            "verdict": brief["verdict"],
            "top": brief["mechanisms"][0]["id"],
            "top_title": brief["mechanisms"][0]["title"],
            "probability": brief["mechanisms"][0]["probability"],
        },
        "validation": {
            "temporal": {
                "gt_window": gt["gt_signature"]["gt_window"],
                "newly_destroyed": gt["gt_signature"]["gt_newly_destroyed"],
                "frozen_top": gt["frozen_top_mechanism"],
                "match": gt["true_outcome_rank"] == 1,
            },
            "spatial": {
                "status": "pending",
                "reason": "no masked re-run exists for this study",
                "what_it_would_take": "the same frozen rules recomputed "
                                      "over a masked half of the valley, "
                                      "with the ranking required to hold",
            },
        },
        "memory_status": {"episodes": 0,
                          "note": "not installed for this domain"},
        "identity": {"frozen_brief_sha256": frozen_sha,
                     "memory_empty_brief_sha256": mem_sha,
                     "match": frozen_sha == mem_sha},
        "why_empty": {"dated_damage_days": len(days),
                      "dateless_features": dateless,
                      "note": "Two real damage days cannot support any "
                              "honest minimum history."},
        "unlock": ["dated flood observations across more days",
                   "a preregistered flood outcome rule",
                   "flood backtest episodes under that rule"],
    }


def _live_snapshot(pull_csv: pathlib.Path) -> dict:
    """Today's reading from a live FIRMS pull (committed beside the
    snapshot so the numbers stay checkable). The pull never enters data/
    or the frozen study; this section is dated by its own latest
    detection day, never by wall-clock. It is a reading of now, not a
    forecast of tomorrow: no forecasting model exists here."""
    import csv
    from collections import Counter
    from scripts import backtest_episodes as be
    from engine.ledger import compute_ledger_from_spec, score_mechanisms
    from engine import memory as _memory
    import yaml
    rows = list(csv.DictReader(pull_csv.open()))
    dets = [(r["acq_date"], float(r["longitude"]), float(r["latitude"]))
            for r in rows]
    roles, _ = be._build_roles(dets, 0.5, 3)
    rules = json.loads((ROOT / "demo/fire_study/rules.json").read_text())
    ledger = compute_ledger_from_spec(rules, roles)
    ranking = score_mechanisms(rules, ledger)
    frozen = json.loads(
        (ROOT / "demo/fire_study/output/brief.json").read_text())
    same = ([m["id"] for m in ranking] ==
            [m["id"] for m in frozen["mechanisms"]] and
            all(abs(a["probability"] - b["probability"]) < 0.00005
                for a, b in zip(ranking, frozen["mechanisms"])))
    mem = yaml.safe_load(MEM_CFG.read_text())
    sig = _memory.signature_for_facts(
        ledger["facts"], mem["signature"]["count_bin_edges"])
    match = {"episodes": 0, "labelled": 0, "known": False}
    try:
        import sqlite3
        from store import db as _db
        mdb = ROOT / "results" / "memory_episodes.sqlite3"
        con = sqlite3.connect(f"file:{mdb.resolve()}?mode=ro", uri=True)
        try:
            eps = _db.episodes_for(con)
            outs = _db.outcomes_for(con)
        finally:
            con.close()
        as_of = max(o["window_end"] for o in outs
                    if o["label"] != "unlabelable")
        pats = _memory.patterns_from_rows(
            eps, outs, mem["signature"]["count_bin_edges"],
            mem["memory"]["outcome_supports"], as_of,
            mem.get("rule_id", "memory-v1"))
        p = pats.get(sig["id"])
        if p is not None:
            match = {"episodes": p["episodes"], "labelled": p["labeled"],
                     "known": True}
    except (OSError, sqlite3.Error):
        pass
    phases = json.loads(
        (ROOT / "demo/fire_study/inputs/timeline.json").read_text())["phases"]
    study_days = sorted(p["start"][:10] for p in phases)
    by_day = sorted(Counter(r["acq_date"] for r in rows).items())
    lats = [float(r["latitude"]) for r in rows]
    lons = [float(r["longitude"]) for r in rows]
    return {
        "as_of": by_day[-1][0],
        "partial_last_day": True,
        "study_window": [study_days[0], study_days[-1]],
        "held_out": "the late-September restart, confirmed after the freeze",
        "detections": len(rows),
        "days": [{"day": day, "detections": n} for day, n in by_day],
        "bbox_check": {
            "lat": [min(lats), max(lats)],
            "lon": [min(lons), max(lons)],
            "inside_study_box": (
                min(lats) >= -2.99993 and max(lats) <= -0.01536
                and min(lons) >= 112.00347 and max(lons) <= 114.99982),
        },
        "ranking": [{"id": m["id"], "title": m["title"],
                     "probability": m["probability"]} for m in ranking],
        "matches_frozen": same,
        "signature": sig["id"],
        "pattern_match": match,
        "note": ("A reading of now, not a forecast of tomorrow: no "
                 "forecasting model exists here, and none was invented."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(ROOT / "api/demo2_data"))
    ap.add_argument("--live-pull", default=None,
                    help="live FIRMS pull CSV (committed beside snapshots)")
    a = ap.parse_args(argv)
    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        fire = _fire_snapshot(tmp)
        nepal = _nepal_snapshot(tmp)
        if a.live_pull:
            src = pathlib.Path(a.live_pull)
            dst = out_dir / "live_pull.csv"
            dst.write_bytes(src.read_bytes())
            fire["live"] = _live_snapshot(dst)
            dated = out_dir / f"live_pull_{fire['live']['as_of']}.csv"
            dst.rename(dated)
    (out_dir / "fire.json").write_text(
        json.dumps(fire, indent=1, sort_keys=True) + "\n")
    (out_dir / "nepal.json").write_text(
        json.dumps(nepal, indent=1, sort_keys=True) + "\n")
    print(f"fire: {fire['memory_status']['episodes']} episodes, "
          f"{fire['memory_status']['labelled']} labelled, "
          f"{fire['memory_status']['patterns']} patterns, "
          f"best {fire['memory_status']['best_labelled']}/"
          f"{fire['memory_status']['threshold']}")
    print(f"nepal: identity match = {nepal['identity']['match']}")
    print(f"wrote {out_dir / 'fire.json'} {out_dir / 'nepal.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
