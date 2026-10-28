"""Durable tests for the setup round (offline; no network, no key).

The live setup rounds are recorded as cassettes and reviewed as artifacts;
what the suite locks in is the validation logic: cite discipline, the open
set, and the null red-team applied to a draft's own weights.
"""
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import setup_study as su

LEDGER = {"F1_total_pre_cutoff_damage", "F2_upstream_share",
          "F3_channel_adjacent_share", "F4_cluster_hit",
          "F5_upstream_density_ratio", "F6_extent_context",
          "F7_target_reach_share", "F8_inputs_audit_clean"}

GOOD = {"mechanisms": [
    {"id": "drain", "title": "safe drainage", "supports": ["F3_channel_adjacent_share"],
     "opposes": ["F4_cluster_hit"], "prior": 1.0},
    {"id": "burst", "title": "ponding then release", "supports": ["F4_cluster_hit"],
     "opposes": [], "prior": 1.0},
    {"id": "quiet", "title": "nothing further happens", "supports": [],
     "opposes": ["F4_cluster_hit"], "prior": 1.0}],
    "weights": {f: 1.0 for f in LEDGER},
    "cluster_rule": {"max_distance_m": 500, "min_features": 8}}


def test_valid_draft_passes():
    import json
    draft, errors = su.validate_draft(json.dumps(GOOD), LEDGER)
    assert draft and errors == []


def test_abbreviated_cites_rejected():
    import copy
    import json
    bad = copy.deepcopy(GOOD)
    bad["mechanisms"][0]["supports"] = ["F3"]
    _, errors = su.validate_draft(json.dumps(bad), LEDGER)
    assert any("F3" in e for e in errors)


def test_missing_quiet_story_rejected():
    import copy
    import json
    bad = copy.deepcopy(GOOD)
    bad["mechanisms"] = [m for m in bad["mechanisms"] if m["id"] != "quiet"]
    _, errors = su.validate_draft(json.dumps(bad), LEDGER)
    assert any("nothing-happens" in e for e in errors)


def test_null_red_team_on_draft_weights():
    ok, top = su.null_test(GOOD)
    assert ok and top == "quiet"


def test_burst_loaded_draft_fails_null():
    import copy
    bad = copy.deepcopy(GOOD)
    bad["mechanisms"] = [m for m in bad["mechanisms"] if m["id"] != "quiet"]
    bad["mechanisms"].append({"id": "calm", "title": "calm water",
                              "supports": [], "opposes": [], "prior": 0.0})
    ok, _ = su.null_test(bad)
    assert not ok
