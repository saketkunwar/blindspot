"""Durable P2 FHZ tests: zone relation sets + story polarity, made real.

Gate reading (see engine/fhz.py): every MUST_BE zone carries a non-empty
E/R/G set (structural — counterparts present, relations computable). No
non-disjointness gate: remote wet zones are legitimately disjoint, and
failing them would mistake geography for broken plumbing. Stories must
cite real fact ids with non-empty supports and a weighted null story.
"""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine import fhz  # noqa: E402

DEMO = ROOT / "demo" / "nepal_cascade"


def _bbox_poly(bbox):
    x0, y0, x1, y1 = bbox
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {"type": "Polygon", "coordinates": [ring]}


def _study_geoms():
    from shapely.geometry import shape as _shape
    from shapely.ops import unary_union
    d = DEMO / "inputs"
    feats = json.loads((d / "pre_t1_features.geojson").read_text())["features"]
    damage = unary_union([_shape(f["geometry"]) for f in feats])
    target = unary_union([_shape(f["geometry"]) for f in
                          json.loads((d / "target_reach.geojson").read_text())["features"]])
    extent = json.loads((d / "extent.json").read_text())
    outline = _shape(_bbox_poly(extent["bbox"]))
    centroid = (outline.centroid.x, outline.centroid.y)
    return damage, target, outline, centroid


def test_split_and_validate_real_zones():
    must_be = json.loads((ROOT / "results" / "flood.json").read_text())["act2"]["must_be"]
    zones = fhz.split_zones(must_be)
    assert len(zones) == 418
    damage, target, outline, centroid = _study_geoms()
    rep = fhz.validate_zones(zones, outline, damage, centroid)
    assert rep["n_zones"] == 418
    # Frozen-data characterization: recompute if study inputs change.
    assert rep["informative_total"] == 518
    for z in rep["zones"]:
        assert set(z["relations"]) == {"E", "R", "G"}


def test_empty_zone_fails_closed():
    with pytest.raises(fhz.ZoneError):
        fhz.split_zones({"type": "Polygon", "coordinates": []})
    with pytest.raises(fhz.ZoneError):
        fhz.validate_zones([{"type": "Point", "coordinates": []}],
                           {"type": "Point", "coordinates": [0, 0]},
                           {"type": "Point", "coordinates": [1, 1]}, (0, 0))


def test_real_stories_clean():
    rules = json.loads((DEMO / "rules.json").read_text())
    brief = json.loads((DEMO / "output" / "brief.json").read_text())
    assert fhz.validate_stories(rules, set(brief["ledger"]["facts"])) == []


def test_bad_stories_flagged():
    rules = json.loads((DEMO / "rules.json").read_text())
    brief = json.loads((DEMO / "output" / "brief.json").read_text())
    fids = set(brief["ledger"]["facts"])
    bad = copy.deepcopy(rules)
    bad["mechanisms"][0]["supports"] = ["no_such_fact"]
    bad["mechanisms"][1]["supports"] = []
    bad["caution_prior"]["weight"] = 0.0
    problems = fhz.validate_stories(bad, fids)
    assert any("no_such_fact" in p for p in problems)
    assert any("empty supports" in p for p in problems)
    assert any("no positive weight" in p for p in problems)
