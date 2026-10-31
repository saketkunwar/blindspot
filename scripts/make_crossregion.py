"""Build the cross-region study snapshot from committed artifacts only.

Reads results/memory_census.json (episodes) and recomputes the per-pattern
scene breakdown under the frozen v4 key — the same computation the
diagnosis ran. Checks data/raw/ for the three pending pulls and reports
their status honestly (pending vs present). No hand-typed numbers.

Usage: python scripts/make_crossregion.py  (writes api/demo2_data/crossregion.json)
"""
import json
import pathlib
import sqlite3
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from engine import memory as _memory  # noqa: E402
from store import db as _db  # noqa: E402

PENDING = {
    "iberia_ext": "data/raw/firms_iberia_ext.csv",
    "texas_ext": "data/raw/firms_texas_ext.csv",
    "quiet": "data/raw/kalimantan_quiet.csv",
}


def main() -> int:
    db_path = ROOT / "results" / "memory_episodes.sqlite3"
    con = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        eps = _db.episodes_for(con)
        outs = _db.outcomes_for(con)
    finally:
        con.close()
    cfg = yaml.safe_load(
        (ROOT / "config" / "preregistered_memory.yaml").read_text())
    unlab = cfg.get("unlabelable_label", "unlabelable")
    edges = cfg["signature"]["count_bin_edges"]
    lab_of = {o["episode_id"]: o["label"] for o in outs}
    for e in eps:
        e["label"] = lab_of.get(e["episode_id"], unlab)
    by_scene = Counter(e["scene"] for e in eps)
    lab_by_scene = Counter(e["scene"] for e in eps
                           if e["label"] != unlab)
    sig_of = {e["episode_id"]: _memory.signature_for_facts(
        e.get("facts") or {}, edges)["id"] for e in eps}
    groups: dict[str, list] = {}
    for e in eps:
        groups.setdefault(sig_of[e["episode_id"]], []).append(e)
    patterns = []
    for pid, members in groups.items():
        labelled = [m for m in members
                    if m["label"] != cfg.get("unlabelable_label",
                                             "unlabelable")]
        scenes = sorted(Counter(m["scene"] for m in members).items())
        patterns.append({"labelled": len(labelled),
                         "episodes": len(members),
                         "scenes": dict(scenes)})
    patterns.sort(key=lambda p: (-p["labelled"], -p["episodes"]))
    out = {
        "episodes": len(eps),
        "labelled": sum(1 for e in eps if e["label"] != cfg.get(
            "unlabelable_label", "unlabelable")),
        "patterns": len(patterns),
        "cross_scene": sum(1 for p in patterns if len(p["scenes"]) > 1),
        "scenes": [{"scene": s, "episodes": by_scene[s],
                    "labelled": lab_by_scene.get(s, 0)}
                   for s in sorted(by_scene)],
        "top_patterns": patterns[:8],
        "speak_bar": cfg["memory"]["min_episodes_to_speak"],
        "pending_pulls": {k: ("present" if (ROOT / v).exists() else "pending")
                          for k, v in PENDING.items()},
        "provenance": {
            "results/memory_episodes.sqlite3": _sha(db_path),
            "config/preregistered_memory.yaml": _sha(
                ROOT / "config/preregistered_memory.yaml"),
        },
    }
    dest = ROOT / "api" / "demo2_data" / "crossregion.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    assert json.loads(dest.read_text()) == out
    lead = patterns[0]
    print(f"crossregion: {out['episodes']} eps, {out['patterns']} patterns, "
          f"{out['cross_scene']} cross-scene; leader {lead['labelled']} "
          f"labelled of bar {out['speak_bar']}")
    print(f"wrote {dest}")
    return 0


def _sha(path: pathlib.Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
