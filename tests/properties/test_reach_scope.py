"""Durable P2 reach-scope tests: spatial network scoping without watershed ids.

The data carries no WATERSHED.permanent_id / reach_code keys (OSM tags
only), so scopes derive from geometry: target-tributary (near the target
reach), else upstream/downstream of the flood centroid latitude. The
frozen ledger path is untouched — scoping is additive diagnostics.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.ledger import (  # noqa: E402
    REACH_CODES,
    _resolve_geometry,
    network_reach_report,
    tag_network_reaches,
    with_reach_tags,
)

DEMO = ROOT / "demo" / "nepal_cascade"


def _inputs():
    d = DEMO / "inputs"
    feats = json.loads((d / "pre_t1_features.geojson").read_text())["features"]
    network = json.loads((d / "waterways.geojson").read_text())
    target = json.loads((d / "target_reach.geojson").read_text())["features"]
    return feats, network, target


def _bbox_poly(bbox):
    x0, y0, x1, y1 = bbox
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {"type": "Polygon", "coordinates": [ring]}


def _split_lat():
    from shapely.geometry import shape as _shape
    from engine import facts as _facts
    extent = json.loads((DEMO / "inputs" / "extent.json").read_text())
    box = _shape(_bbox_poly(extent["bbox"]))
    return _facts._project(box).centroid.y


def test_codes_partition_network():
    _, network, target = _inputs()
    codes = tag_network_reaches(network, target, _split_lat(), 50.0)
    assert len(codes) == 400
    assert set(codes) <= set(REACH_CODES)
    assert set(codes) == set(REACH_CODES)  # all three scopes occur
    tagged = with_reach_tags(network, codes)
    assert len(tagged["features"]) == 400
    assert all(f["properties"]["_reach"] in REACH_CODES
               for f in tagged["features"])


def test_report_structure_and_ranges():
    feats, network, target = _inputs()
    split_lat = _split_lat()
    domain = json.loads((DEMO / "domain.json").read_text())
    adj_m, _, _ = _resolve_geometry(
        json.loads((DEMO / "rules.json").read_text()), domain)
    rep = network_reach_report(feats, network, target, None, split_lat, adj_m)
    assert rep["scopes"] == ["downstream", "target", "upstream"]
    assert sum(v["n_network"] for v in rep["by_reach"].values()) == 400
    for v in rep["by_reach"].values():
        assert 0.0 <= v["near_share"] <= 1.0
        assert 0 <= v["near_count"] <= len(feats)


def test_reach_audit_leaves_frozen_brief_untouched(tmp_path):
    from agents import autoinsight as _ai
    out = tmp_path / "brief.json"
    brief = _ai.run(DEMO / "inputs", DEMO / "rules.json", out, tmp_path,
                    model_round="off", reach_audit_path=tmp_path / "reach.json")
    frozen = json.loads((DEMO / "output" / "brief.json").read_text())
    strip = lambda b: {k: v for k, v in b.items() if k != "model_round"}
    assert strip(brief) == strip(frozen)
    reach = json.loads((tmp_path / "reach.json").read_text())
    assert reach["scopes"] == ["downstream", "target", "upstream"]
