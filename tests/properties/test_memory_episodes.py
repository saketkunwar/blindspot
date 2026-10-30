"""M0 memory episodes: leakage-cutoff behavior and census determinism.

Leakage: an episode at cutoff C must be identical whether the scene file
holds only days <= C or the full scene (post-cutoff bytes must not move the
ranking, the cell grid, or the counts). Determinism: two runs into two
databases must yield identical censuses (timestamps excluded).
"""
import json
import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import backtest_episodes as be  # noqa: E402
from store import db  # noqa: E402

SCENE = ROOT / "data/fire_kalimantan/firms_kalimantan_c.json"
RULES = json.loads((ROOT / "demo/fire_study/rules.json").read_text())
MEM = yaml.safe_load((ROOT / "config/preregistered_memory.yaml").read_text())


def _run(db_path, scenes):
    argv = ["--db", str(db_path), "--rules", str(ROOT / "demo/fire_study/rules.json"),
            "--memory-config", str(ROOT / "config/preregistered_memory.yaml"),
            "--no-manifest-check"]
    for s in scenes:
        argv += ["--scene", str(s)]
    assert be.main(argv) == 0
    con = db.connect(db_path)
    try:
        return db.census(con), db.episodes_for(con), db.outcomes_for(con)
    finally:
        con.close()


def _truncated_scene(tmp_path, cutoff):
    """Scene copy holding only detections on/before cutoff (leakage probe)."""
    obj = json.loads(SCENE.read_text())
    recs = [r for r in obj["detections"]
            if str((r.get("payload") or {}).get("acq_date", ""))[:10] <= cutoff]
    assert 0 < len(recs) < len(obj["detections"])
    obj = dict(obj)
    obj["detections"] = recs
    p = tmp_path / f"trunc_{cutoff}.json"
    p.write_text(json.dumps(obj))
    return p


def test_episode_uses_only_pre_cutoff_data(tmp_path):
    """Episode rows carry exactly the pre-cutoff slice: counts, days, and
    the recomputed cell grid match the raw scene filtered to day <= cutoff,
    and no stored day exceeds the cutoff."""
    census, episodes, _ = _run(tmp_path / "a.sqlite3", [SCENE])
    from pipelines.loader import parse_firms_detections
    dets = parse_firms_detections(json.loads(SCENE.read_text()))
    grid = MEM["curation_mirror"]["grid_cell_deg"]
    import hashlib
    import math
    scene_sha = hashlib.sha256(SCENE.read_bytes()).hexdigest()
    assert census, "expected a non-empty census"
    for ep in episodes:
        c = ep["cutoff"]
        pre = [(d, lo, la) for d, lo, la in dets if d <= c]
        assert ep["n_pre"] == len(pre)
        assert ep["days_pre"] == sorted({d for d, _, _ in pre})
        assert all(d <= c for d in ep["days_pre"])
        cells = {f"{math.floor(lo / grid) * grid:.1f},"
                 f"{math.floor(la / grid) * grid:.1f}"
                 for _, lo, la in pre}
        assert ep["cells_pre"] == len(cells)
        assert ep["scene_sha256"] == scene_sha


def test_post_cutoff_bytes_do_not_move_episodes(tmp_path):
    """Truncating the scene at each cutoff leaves that cutoff's episode
    (facts, ranking, top, counts) byte-identical: the ranking is frozen from
    pre-cutoff data only."""
    _, full_eps, _ = _run(tmp_path / "full.sqlite3", [SCENE])
    full = {e["episode_id"]: e for e in full_eps}
    max_day = max(e["cutoff"] for e in full_eps)
    for ep in full_eps:
        if ep["cutoff"] == max_day:
            continue  # no post-cutoff bytes exist to remove; nothing to prove
        trunc = _truncated_scene(tmp_path, ep["cutoff"])
        _, eps, _ = _run(tmp_path / f"t_{ep['cutoff']}.sqlite3", [trunc])
        assert len(eps) >= 1
        got = next(e for e in eps if e["cutoff"] == ep["cutoff"])
        for key in ("n_pre", "days_pre", "cells_pre", "facts",
                    "ranking", "top_mechanism"):
            assert got[key] == ep[key], (ep["cutoff"], key)


def test_unlabelable_episodes_are_kept(tmp_path):
    """Episodes whose look-ahead window outruns the scene stay in the census
    as unlabelable instead of being dropped."""
    census, _, _ = _run(tmp_path / "a.sqlite3", [SCENE])
    unl = [r for r in census if r["label"] == MEM["unlabelable_label"]]
    assert unl, "expected at least one unlabelable episode"
    assert len(census) == len([r for r in census if r["episode_id"]])
    for r in unl:
        assert r["window_end"] > max(x["cutoff"] for x in census
                                     if x["scene"] == r["scene"])


def test_census_is_deterministic(tmp_path):
    """Two runs produce identical censuses (timestamps excluded by design)."""
    c1, e1, o1 = _run(tmp_path / "a.sqlite3", [SCENE])
    c2, e2, o2 = _run(tmp_path / "b.sqlite3", [SCENE])
    assert c1 == c2
    strip = lambda rows: [{k: v for k, v in r.items() if k != "recorded_at"}
                          for r in rows]
    assert strip(e1) == strip(e2)
    assert strip(o1) == strip(o2)


def test_full_cutoff_matches_frozen_brief():
    """The episode at the scene's max day reproduces the frozen study brief
    ledger values and top mechanism: the M0 ranking path is the study path."""
    import sqlite3
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        c, e, _ = _run(pathlib.Path(td) / "x.sqlite3", [SCENE])
    last = max(e, key=lambda r: r["cutoff"])
    brief = json.loads((ROOT / "demo/fire_study/output/brief.json").read_text())
    frozen = brief["ledger"]["facts"]
    for fid, f in frozen.items():
        assert last["facts"][fid]["value"] == f["value"], fid
        assert last["facts"][fid]["active"] == f["active"], fid
    assert last["top_mechanism"] == brief["mechanisms"][0]["id"]


def test_duplicate_outcome_is_rejected(tmp_path):
    """One row per (episode, rule): a second outcome for the same episode
    and rule fails instead of fanning out the census join."""
    import sqlite3

    con = db.connect(tmp_path / "dup.sqlite3")
    try:
        db.add_episode(con, "scene@2026-09-17", "scene", "0" * 64,
                       "2026-09-17", 1, ["2026-09-17"], 1, {}, [], "m")
        db.add_outcome(con, "scene@2026-09-17", MEM["rule_id"], 2,
                       "2026-09-18", "2026-09-19", 3, "restart")
        with pytest.raises(sqlite3.IntegrityError):
            db.add_outcome(con, "scene@2026-09-17", MEM["rule_id"], 2,
                           "2026-09-18", "2026-09-19", 3, "restart")
    finally:
        con.close()


def test_store_stays_insert_only():
    """New accessors add no update/delete/drop path."""
    exposed = [n for n in dir(db)
               if "update" in n or "delete" in n or "drop" in n]
    assert exposed == []
