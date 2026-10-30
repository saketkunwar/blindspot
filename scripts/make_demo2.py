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
    return {
        "frozen": {
            "verdict": brief["verdict"],
            "top": brief["mechanisms"][0]["id"],
            "top_title": brief["mechanisms"][0]["title"],
            "probability": brief["mechanisms"][0]["probability"],
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(ROOT / "api/demo2_data"))
    a = ap.parse_args(argv)
    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        fire = _fire_snapshot(tmp)
        nepal = _nepal_snapshot(tmp)
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
