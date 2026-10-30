"""M3 evolution discipline: checks bite, caps hold, humans decide.

Structural validation rejects multi-change, unknown-kind, low-recurrence,
and ghost-cited proposals; the per-run cap holds; time slices split
old-to-new; the Skeptic's replay math is exact on synthetic histories; the
review CLI refuses every unsafe approval path and records verdicts; setup
rounds log exactly one trace row. Synthetic labels below are mechanical
test fixtures for machinery, never observations.
"""
import hashlib
import json
import pathlib
import sqlite3
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine import evolution as evo  # noqa: E402
from store import db  # noqa: E402

MEM = yaml.safe_load((ROOT / "config/preregistered_memory.yaml").read_text())
EVO = MEM["evolver"]
FIRE_RULES = json.loads((ROOT / "demo/fire_study/rules.json").read_text())
FIRE_SHA = hashlib.sha256(
    (ROOT / "demo/fire_study/rules.json").read_bytes()).hexdigest()
SHAS = {"fire_study": FIRE_SHA, "nepal_cascade": "0" * 64}

SUPPORTS = {"go": ["m_win"], "stop": ["m_lose"]}


def _good_prop(**over):
    p = {"track": "B", "status": "pending",
         "issue": "Weights under-serve the pattern in three slides.",
         "recurrence": 3,
         "change": {"weight": {"fact_id": "FF4_hotspot_clumping",
                               "old_weight": 2.0, "new_weight": 2.5}},
         "cited_episodes": ["s@2026-09-17"],
         "cited_traces": [1],
         "rejected": ["neighboring slide (shared data)"],
         "base_rules_sha": FIRE_SHA}
    p.update(over)
    return p


def _ctx():
    return {"s@2026-09-17"}, {1}, EVO, SHAS


def test_good_proposal_passes():
    assert evo.validate_proposal(_good_prop(), *_ctx()) == []


def test_structural_rejections():
    eps, tr, cfg, shas = _ctx()
    assert evo.validate_proposal(_good_prop(status="candidate"), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(_good_prop(track="Z"), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(
        _good_prop(change={"weight": {"fact_id": "FF4_hotspot_clumping",
                                      "old_weight": 2.0, "new_weight": 2.5},
                           "other": {}}), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(
        _good_prop(change={"mechanism": {"add": "m_new"}}), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(_good_prop(recurrence=2), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(
        _good_prop(cited_episodes=["ghost@2026-09-17"]), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(_good_prop(cited_traces=[99]), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(_good_prop(issue="  "), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(
        _good_prop(change={"weight": {"fact_id": "FF4_hotspot_clumping",
                                      "old_weight": 2.0, "new_weight": 2.0}}),
        eps, tr, cfg, shas) != []
    assert evo.validate_proposal(
        _good_prop(change={"weight": {"fact_id": "FF4_hotspot_clumping",
                                      "old_weight": -1.0, "new_weight": 2.5}}),
        eps, tr, cfg, shas) != []
    assert evo.validate_proposal(_good_prop(rejected="none"), eps, tr, cfg, shas) != []
    assert evo.validate_proposal(_good_prop(base_rules_sha="1" * 64),
                                  eps, tr, cfg, shas) != []


def test_cap_and_slices():
    kept, dropped = evo.cap_proposals([1, 2, 3], 1)
    assert kept == [1] and dropped == 2
    assert evo.cap_proposals([], 1) == ([], 0)
    days = ["2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20",
            "2026-09-21"]
    assert evo.independent_cutoffs(
        ["2026-09-17", "2026-09-18", "2026-09-20"], 2) == \
        ["2026-09-17", "2026-09-20"]
    spans = evo.time_slices(days, 0.4, 0.4)
    assert spans == {"propose": ["2026-09-17", "2026-09-18"],
                     "validate": ["2026-09-19", "2026-09-20"],
                     "final": ["2026-09-21"]}
    thin = evo.time_slices(["2026-09-17", "2026-09-18"], 0.4, 0.4)
    assert thin["validate"] == [] and thin["final"] == []


def test_apply_weight_change():
    change = {"weight": {"fact_id": "FF4_hotspot_clumping",
                         "old_weight": 2.0, "new_weight": 2.5}}
    new_rules = evo.apply_weight_change(FIRE_RULES, change)
    assert new_rules["facts"]["FF4_hotspot_clumping"]["weight"] == 2.5
    assert FIRE_RULES["facts"]["FF4_hotspot_clumping"]["weight"] == 2.0
    with pytest.raises(ValueError):
        evo.apply_weight_change(FIRE_RULES, {"weight": {
            "fact_id": "FF4_hotspot_clumping", "old_weight": 9.0,
            "new_weight": 2.5}})
    with pytest.raises(KeyError):
        evo.apply_weight_change(FIRE_RULES, {"weight": {
            "fact_id": "FF9_ghost", "old_weight": 1.0, "new_weight": 2.0}})


def _synthetic_rules():
    return {
        "facts": {"F1": {"weight": 1.0}},
        "mechanisms": [
            {"id": "m_win", "title": "W", "prior": 0.0, "supports": ["F1"]},
            {"id": "m_lose", "title": "L", "prior": 0.5, "supports": []}],
        "ledger_spec": {"facts": {
            "F1": {"op": "count", "params": {"role": "dots", "min_count": 1},
                   "text": "{value}"}}},
    }


def _roles_fn(ep):
    return {"dots": {"type": "FeatureCollection",
                     "features": [{"type": "Feature", "properties": {},
                                   "geometry": None},
                                  {"type": "Feature", "properties": {},
                                   "geometry": None}]}}


def _syn_eps(n, label):
    eps = [{"episode_id": f"s@day{i}", "cutoff": f"2026-10-{10 + i:02d}"}
           for i in range(n)]
    return eps, {e["episode_id"]: label for e in eps}


def test_skeptic_replay_win_and_lose():
    rules = _synthetic_rules()
    change = {"weight": {"fact_id": "F1", "old_weight": 1.0,
                         "new_weight": 0.1}}
    eps, outs = _syn_eps(3, "stop")  # base top m_win never backed
    win = evo.skeptic_replay(rules, change, eps, outs, SUPPORTS, _roles_fn)
    assert win["episodes"] == 3
    assert win["base_rate"] == 0.0 and win["proposed_rate"] == 1.0
    assert win["edge"] == 1.0
    assert [m["now"] for m in win["moved_tops"]] == ["m_lose"] * 3
    eps2, outs2 = _syn_eps(3, "go")  # base already right; change hurts
    lose = evo.skeptic_replay(rules, change, eps2, outs2, SUPPORTS,
                              _roles_fn)
    assert lose["edge"] == -1.0
    assert lose["base_rules_sha"] == win["base_rules_sha"]


def test_evolution_store_round_trip(tmp_path):
    con = db.connect(tmp_path / "evo.sqlite3")
    try:
        t = db.add_trace(con, "lbl", "setup_draft", 0, "req", "resp",
                         ["v1"], "failed_checks", 12)
        assert [r["rowid"] for r in db.traces_for(con)] == [t]
        p = db.add_proposal(con, "B", "candidate", "issue", 3, {},
                            ["s@2026-09-17"], [t], [], FIRE_SHA)
        props = db.proposals_for(con)
        assert len(props) == 1 and props[0]["status"] == "candidate"
        assert json.loads(props[0]["change_json"]) == {}
        r = db.add_replay(con, p, {"edge": 0.0})
        assert db.replays_for(con, p)[0]["rowid"] == r
        v = db.add_verdict(con, p, "reject", "not enough evidence", "op")
        assert db.verdicts_for(con, p)[0]["rowid"] == v
        exposed = [n for n in dir(db)
                   if "update" in n or "delete" in n or "drop" in n]
        assert exposed == []
    finally:
        con.close()


def _run_cli(*args, cwd=ROOT):
    import subprocess
    return subprocess.run([sys.executable, "scripts/review_proposals.py", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=300)


def _submit_payload(tmp_path, **over):
    from scripts import backtest_episodes as be
    medb = tmp_path / "mem.sqlite3"
    be.main(["--db", str(medb), "--rules",
             str(ROOT / "demo/fire_study/rules.json"), "--memory-config",
             str(ROOT / "config/preregistered_memory.yaml"),
             "--no-manifest-check", "--scene",
             str(ROOT / "data/fire_kalimantan/firms_kalimantan_c.json")])
    payload = {"track": "B", "status": "pending",
               "issue": "Hotspot weight under-serves restart slides.",
               "recurrence": 3,
               "change": {"weight": {"fact_id": "FF4_hotspot_clumping",
                                     "old_weight": 2.0, "new_weight": 2.5}},
               "cited_episodes": ["kalimantan_c@2026-09-17"],
               "cited_traces": [], "rejected": [],
               "base_rules_sha": FIRE_SHA}
    payload.update(over)
    return medb, payload


def test_review_cli_refusal_paths(tmp_path):
    evodb = tmp_path / "evo.sqlite3"
    medb, payload = _submit_payload(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(
        payload, change={"weight": {"fact_id": "FF4_hotspot_clumping",
                                    "old_weight": 2.0, "new_weight": 2.5},
                         "extra": {}})))
    r = _run_cli("--db", str(evodb), "submit", "--file", str(bad),
                 "--memory-db", str(medb))
    assert r.returncode == 2  # multi-change refused
    good = tmp_path / "good.json"
    good.write_text(json.dumps(payload))
    r = _run_cli("--db", str(evodb), "submit", "--file", str(good),
                 "--memory-db", str(medb))
    assert r.returncode == 0, r.stdout + r.stderr
    r = _run_cli("--db", str(evodb), "replay", "--id", "1",
                 "--memory-db", str(medb))
    assert r.returncode == 0, r.stdout + r.stderr
    result = json.loads(r.stdout)
    assert result["episodes"] == 0  # real validation span has no labels yet
    r = _run_cli("--db", str(evodb), "approve", "--id", "1")
    assert r.returncode == 2  # no reason
    r = _run_cli("--db", str(evodb), "approve", "--id", "1",
                 "--reason", "looks fine")
    assert r.returncode == 2  # replay clears nothing, no override
    r = _run_cli("--db", str(evodb), "approve", "--id", "99",
                 "--reason", "x", "--override", "y")
    assert r.returncode == 2  # unknown proposal
    r = _run_cli("--db", str(evodb), "reject", "--id", "1")
    assert r.returncode == 2  # reason required
    r = _run_cli("--db", str(evodb), "reject", "--id", "1",
                 "--reason", "validation span is empty; nothing earned")
    assert r.returncode == 0, r.stdout + r.stderr
    r = _run_cli("--db", str(evodb), "reject", "--id", "1",
                 "--reason", "again")
    assert r.returncode == 2  # already decided
    r = _run_cli("--db", str(evodb), "approve", "--id", "1",
                 "--reason", "late", "--override", "late override")
    assert r.returncode == 2  # decided proposals stay decided


def test_review_approve_override_records_loudly(tmp_path):
    evodb = tmp_path / "evo.sqlite3"
    medb, payload = _submit_payload(tmp_path)
    good = tmp_path / "good.json"
    good.write_text(json.dumps(payload))
    assert _run_cli("--db", str(evodb), "submit", "--file", str(good),
                    "--memory-db", str(medb)).returncode == 0
    assert _run_cli("--db", str(evodb), "replay", "--id", "1",
                    "--memory-db", str(medb)).returncode == 0
    out = tmp_path / "proposed.json"
    r = _run_cli("--db", str(evodb), "approve", "--id", "1",
                 "--reason", "operator judgement", "--override",
                 "testing the override path", "--out", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    wrote = json.loads(out.read_text())
    assert wrote["facts"]["FF4_hotspot_clumping"]["weight"] == 2.5
    con = db.connect(evodb)
    try:
        verdicts = db.verdicts_for(con, 1)
        assert len(verdicts) == 1 and verdicts[0]["decision"] == "approve"
        assert "OVERRIDE" in verdicts[0]["reason"]
    finally:
        con.close()


def test_hill_climb_cap_and_as_of(tmp_path):
    import subprocess
    from scripts import hill_climb as hc
    tdb = tmp_path / "traces.sqlite3"
    con = db.connect(tdb)
    try:
        for i in range(3):
            db.add_trace(con, "lbl", "setup_draft", 0, f"reqA{i}", "resp",
                         ["same violation"], "failed_checks", 5)
        for i in range(3):
            db.add_trace(con, "lbl", "setup_draft", 0, f"reqB{i}", "resp",
                         ["other violation"], "failed_checks", 5)
        con.commit()
    finally:
        con.close()
    evo_db = tmp_path / "evo.sqlite3"
    r = subprocess.run(
        [sys.executable, "scripts/hill_climb.py", "--traces-db", str(tdb),
         "--evolver-db", str(evo_db)], cwd=ROOT, capture_output=True,
        text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    report = json.loads(r.stdout)
    assert report["candidates_found"] == 2
    assert report["candidates_filed"] == 1  # cap holds
    assert report["dropped_over_cap"] == 1
    con = db.connect(evo_db)
    try:
        assert len(db.proposals_for(con)) == 1
    finally:
        con.close()
    # Empty inputs: the correct negative, byte-stable across rebuilds.
    r1 = subprocess.run(
        [sys.executable, "scripts/hill_climb.py", "--traces-db",
         str(tmp_path / "none.sqlite3"), "--evolver-db",
         str(tmp_path / "e1.sqlite3")], cwd=ROOT, capture_output=True,
        text=True, timeout=300)
    r2 = subprocess.run(
        [sys.executable, "scripts/hill_climb.py", "--traces-db",
         str(tmp_path / "none.sqlite3"), "--evolver-db",
         str(tmp_path / "e2.sqlite3")], cwd=ROOT, capture_output=True,
        text=True, timeout=300)
    assert r1.returncode == r2.returncode == 0
    assert json.loads(r1.stdout)["candidates_filed"] == 0
    assert r1.stdout == r2.stdout


def test_setup_round_logs_single_trace(tmp_path, monkeypatch):
    import agents.setup_study as ss
    calls = []
    import agents.model_call as mc
    real = mc.complete

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(mc, "complete", counting)
    tdb = tmp_path / "traces.sqlite3"
    rc = ss.main(["--inputs", "demo/nepal_cascade/inputs",
                  "--domain", "demo/nepal_cascade/domain.json",
                  "--frozen-rules", "demo/nepal_cascade/rules.json",
                  "--brief", "demo/nepal_cascade/output/brief.json",
                  "--out-dir", str(tmp_path / "setup"), "--no-card",
                  "--traces-db", str(tdb), "--traces-label", "flood"])
    assert rc == 0
    assert len(calls) == 1  # single-turn by construction, not by hope
    con = db.connect(tdb)
    try:
        rows = db.traces_for(con)
        assert len(rows) == 1
        row = rows[0]
        assert row["role"] == "setup_draft" and row["iteration"] == 0
        assert row["stopped_because"] == "satisfied"
    finally:
        con.close()
