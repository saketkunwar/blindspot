"""Parity: engine/facts.py reproduces the flood ledger from curated inputs."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import autoinsight as ai
from engine import facts

DEMO = ROOT / "demo" / "nepal_cascade"
INPUTS = DEMO / "inputs"


def _roles():
    domain = json.loads((DEMO / "domain.json").read_text())
    return facts.load_inputs_by_role(domain, INPUTS)


def _ledger():
    rules = json.loads((DEMO / "rules.json").read_text())
    roles = _roles()
    feats = roles["damage"]["features"]
    extent = roles["boundary"]
    extent_geom = {"type": "Polygon", "coordinates": [[
        [extent["bbox"][0], extent["bbox"][1]],
        [extent["bbox"][2], extent["bbox"][1]],
        [extent["bbox"][2], extent["bbox"][3]],
        [extent["bbox"][0], extent["bbox"][3]],
        [extent["bbox"][0], extent["bbox"][1]]]]}
    return rules, ai.compute_ledger(
        feats, roles["network"], roles["target"]["features"],
        extent_geom, rules)


def test_closed_op_set():
    assert sorted(facts.OPS) == [
        "area_mean", "area_sum", "cluster", "count",
        "half_share", "near_share", "spread", "time_stats",
    ]


def test_f1_total_count_parity():
    roles = _roles()
    value, active = facts.evaluate(
        "count", roles, {"role": "damage", "min_count": 1})
    assert (value, active) == (2092, True)
    assert value == _ledger()[1]["facts"]["F1_total_pre_cutoff_damage"]["value"]


def test_f2_upstream_share_parity():
    roles = _roles()
    value, active = facts.evaluate("half_share", roles, {
        "role": "damage", "boundary_role": "boundary",
        "axis": "lat", "mode": "share", "threshold": 0.5})
    assert value == 0.5148
    assert active is True
    assert value == _ledger()[1]["facts"]["F2_upstream_share"]["value"]


def test_f3_channel_adjacent_share_parity():
    roles = _roles()
    value, active = facts.evaluate("near_share", roles, {
        "source_role": "damage", "ref_role": "network",
        "distance_m": 250, "threshold": 0.05})
    assert value == 0.7285
    assert active is True
    assert value == _ledger()[1]["facts"]["F3_channel_adjacent_share"]["value"]


def test_f4_cluster_hit_parity():
    roles = _roles()
    value, active = facts.evaluate("cluster", roles, {
        "source_role": "damage", "ref_role": "target",
        "distance_m": 500, "min_features": 8})
    assert (value, active) == (34, True)
    assert value == _ledger()[1]["facts"]["F4_cluster_hit"]["value"]
    # Same count through the network role with a target-name filter.
    rules = json.loads((DEMO / "rules.json").read_text())
    v2, a2 = facts.evaluate("cluster", roles, {
        "source_role": "damage", "ref_role": "network",
        "distance_m": float(rules["cluster_rule"]["max_distance_m"]),
        "min_features": int(rules["cluster_rule"]["min_features"]),
        "ref_filter": {"property": rules["cluster_rule"]["target_property"],
                       "value": rules["cluster_rule"]["target_value"]}})
    assert (v2, a2) == (34, True)


def test_f5_upstream_density_ratio_parity():
    roles = _roles()
    value, active = facts.evaluate("half_share", roles, {
        "role": "damage", "boundary_role": "boundary",
        "axis": "lat", "mode": "density_ratio", "threshold": 1})
    assert value == 1.061
    assert active is True
    assert value == _ledger()[1]["facts"]["F5_upstream_density_ratio"]["value"]


def test_f6_extent_area_parity():
    roles = _roles()
    value, active = facts.evaluate("area_sum", roles, {"role": "boundary"})
    assert (value, active) == (4342540316.7, True)
    assert value == _ledger()[1]["facts"]["F6_extent_context"]["value"]
    mean, _ = facts.evaluate("area_mean", roles, {"role": "boundary"})
    assert mean == value  # single bbox-rectangle feature


def test_f7_target_reach_share_parity():
    roles = _roles()
    value, active = facts.evaluate("near_share", roles, {
        "source_role": "damage", "ref_role": "target",
        "distance_m": 500, "threshold": 0.05})
    assert value == 0.0163
    assert active is False  # below the 0.05 caller threshold, as in the ledger
    assert value == _ledger()[1]["facts"]["F7_target_reach_share"]["value"]


def test_thresholds_come_from_caller():
    roles = _roles()
    value, active = facts.evaluate("near_share", roles, {
        "source_role": "damage", "ref_role": "target",
        "distance_m": 500, "threshold": 0.01})
    assert value == 0.0163
    assert active is True  # same value, looser caller threshold
    _, inactive = facts.evaluate("count", roles,
                                 {"role": "damage", "min_count": 10**9})
    assert inactive is False


def test_time_stats_and_spread_run_on_curated():
    roles = _roles()
    value, active = facts.evaluate("time_stats", roles, {
        "role": "damage", "time_field": "destruction_interval_end",
        "min_distinct": 1})
    assert value["n_total"] == 2092
    assert value["n_dated"] == 0  # curated inputs strip timestamps
    assert active is False
    spread, ok = facts.evaluate("spread", roles, {"role": "damage"})
    assert spread["dx_m"] > 0 and spread["dy_m"] > 0 and ok is True
    assert len(spread["bbox_lonlat"]) == 4


def test_unknown_op_rejected():
    try:
        facts.evaluate("no_such_op", _roles(), {})
    except ValueError:
        pass
    else:
        raise AssertionError("closed op set must reject unknown ops")
