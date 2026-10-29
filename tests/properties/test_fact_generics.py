"""Pins the three Demo 2 learnings as generic fact/ledger behaviour.

These regressions came out of the Kalimantan fire study but must hold for
every study: the flood pipeline (frozen path) shares the same op registry.
"""
from engine import facts as F
from engine.ledger import compute_ledger_from_spec


def _feat(x, y, props=None):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [x, y]},
            "properties": props or {}}


def test_cluster_ref_role_with_filter():
    # op 'cluster' may count against a scoped cell list (ref_) instead of
    # full inputs (inputs_); no domain-specific op needed.
    inputs = {
        "pts": [_feat(0, 0), _feat(0.0005, 0.0005), _feat(5, 5)],
        "cells": [_feat(0, 0, {"hot": True}), _feat(500, 500, {"hot": False})],
    }
    params = {"distance_m": 200, "min_features": 1, "ref_role": "cells",
              "source_role": "pts",
              "ref_filter": {"property": "hot", "value": True}}
    value, ok = F.evaluate("cluster", inputs, params)
    assert ok and value == 2  # only points near the hot cell count


def test_op_time_stats_scale_divides():
    # 'scale' converts raw epoch seconds (e.g. /86400 -> days) generically.
    inputs = {"ev": [_feat(0, 0, {"t": 0}), _feat(0, 0, {"t": 86400})]}
    params = {"role": "ev", "time_field": "t", "min_distinct": 2, "scale": 86400}
    value, ok = F.evaluate("time_stats", inputs, params)
    assert ok and value["max_gap_s"] == 1.0 and value["span_s"] == 1.0


def test_spec_weights_live_inside_facts():
    # weights are per-fact attributes read from facts{}, never a parallel
    # top-level block that can drift out of sync.
    rules = {
        "facts": {
            "A": {"op": "count", "params": {"role": "x", "min_count": 1}, "weight": 3.0},
            "B": {"op": "count", "params": {"role": "x", "min_count": 99}, "weight": 1.0},
        },
        "ledger_spec": {
            "facts": {
                "A": {"op": "count", "params": {"role": "x", "min_count": 1},
                      "text": "{value} xs"},
                "B": {"op": "count", "params": {"role": "x", "min_count": 99},
                      "text": "{value} xs"},
            }
        },
    }
    ledger = compute_ledger_from_spec(rules, {"x": [_feat(0, 0)]})
    assert ledger["facts"]["A"]["active"] is True
    assert ledger["facts"]["A"]["text"] == "1 xs"
    assert ledger["facts"]["B"]["active"] is False
    assert rules["facts"]["A"]["weight"] == 3.0  # scoring reads this, not a twin block
