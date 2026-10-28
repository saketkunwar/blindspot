"""Durable tests for the Nepal-cascade autoinsight demo.

Locks in: pre-cutoff purity of curated inputs, open mechanism set with real
no-event weight, prompt anonymization, determinism, GT quarantine, and the
null red-team (a quiet synthetic world must rank 'nothing happens' first --
proving no outcome was pre-loaded).
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import autoinsight as ai

DEMO = ROOT / "demo" / "nepal_cascade"
INPUTS = DEMO / "inputs"


def _rules():
    return json.loads((DEMO / "rules.json").read_text())


def _ledger():
    rules = _rules()
    feats = json.loads((INPUTS / "pre_t1_features.geojson").read_text())["features"]
    waterways = json.loads((INPUTS / "waterways.geojson").read_text())
    target = json.loads((INPUTS / "target_reach.geojson").read_text())["features"]
    extent = json.loads((INPUTS / "extent.json").read_text())
    extent_geom = {"type": "Polygon", "coordinates": [[
        [extent["bbox"][0], extent["bbox"][1]], [extent["bbox"][2], extent["bbox"][1]],
        [extent["bbox"][2], extent["bbox"][3]], [extent["bbox"][0], extent["bbox"][3]],
        [extent["bbox"][0], extent["bbox"][1]]]]}
    return rules, ai.compute_ledger(feats, waterways, target, extent_geom, rules)


def test_curated_inputs_are_pre_cutoff_only():
    feats = json.loads((INPUTS / "pre_t1_features.geojson").read_text())["features"]
    assert len(feats) > 0
    keys = {k for f in feats for k in (f.get("properties") or {})}
    assert keys <= {"src_id", "feature_type"}, f"leaked properties: {keys}"
    blob = (INPUTS / "pre_t1_features.geojson").read_text()
    assert not re.search(r"\d{4}-\d{2}-\d{2}", blob), "date strings in curated inputs"
    audit = json.loads((INPUTS / "input_audit.json").read_text())
    assert audit["counts"]["kept_pre_cutoff"] == len(feats)


def test_open_mechanism_set_with_live_no_event():
    rules, ledger = _ledger()
    ranking = ai.score_mechanisms(rules, ledger)
    assert len(ranking) == 6
    assert abs(sum(o["probability"] for o in ranking) - 1.0) < 1e-6
    noevent = next(o for o in ranking if o["id"] == "no_further_event")
    assert noevent["probability"] > 0, "no-further-event must carry real weight"


def test_null_red_team_quiet_world_ranks_nothing_first():
    rules = _rules()
    flat = {"facts": {}, "numbers": [], "diagnostics": {}}
    for fid in rules["facts"]:
        flat["facts"][fid] = {"value": 0, "active": False, "text": "synthetic quiet"}
    flat["facts"]["F8_inputs_audit_clean"] = {"value": 1, "active": True, "text": "audit ok"}
    ranking = ai.score_mechanisms(rules, flat)
    assert ranking[0]["id"] == "no_further_event", \
        f"quiet world must rank nothing-first, got {ranking[0]['id']}"


def test_prompt_anonymized_against_inputs():
    rules, ledger = _ledger()
    prompt, _ = ai.build_prompt(rules, ledger)
    forbidden = ai._input_tokens(INPUTS, rules)
    assert len(forbidden) > 20, "token source too thin to prove anything"
    assert ai.audit_prompt(prompt, forbidden) == []


def test_deterministic_byte_identical(tmp_path):
    b1 = tmp_path / "b1.json"
    b2 = tmp_path / "b2.json"
    ai.run(INPUTS, DEMO / "rules.json", b1, tmp_path / "p1", model_round="on")
    ai.run(INPUTS, DEMO / "rules.json", b2, tmp_path / "p2", model_round="on")
    assert b1.read_bytes() == b2.read_bytes()


def test_quarantine_refuses_raw_and_runs_from_copy(tmp_path):
    try:
        ai.run(ROOT / "data" / "raw" / "temporal_data", DEMO / "rules.json",
               tmp_path / "x.json", tmp_path / "px", model_round="off")
    except SystemExit:
        pass
    else:
        raise AssertionError("prediction path must refuse data/raw")
    import shutil
    cp = tmp_path / "inputs_copy"
    shutil.copytree(INPUTS, cp)
    out = tmp_path / "c.json"
    ai.run(cp, DEMO / "rules.json", out, tmp_path / "pc", model_round="on")
    frozen = (DEMO / "output" / "brief.json").read_bytes()
    assert out.read_bytes() == frozen, "relocated inputs must reproduce the frozen brief"
