"""Durable Phase-2 auditor tests. Fail-closed: any red means the auditor is wrong."""
import pathlib

import pytest
from shapely.geometry import Point, box

import engine.gap_auditor as g
from engine.schemas import load_preregistered

ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = load_preregistered(ROOT / "config/preregistered.yaml")


def test_continuity_jump_reports_missing_path():
    t = g.check_continuity("cell", "2026-09-19", "2026-09-20", "NTPP", "DC")
    assert t.kind == "DISCONTINUOUS_JUMP"
    assert t.missing_intermediates == ["TPP", "PO", "EC"]
    ok = g.check_continuity("cell", "2026-09-16", "2026-09-17", "DC", "PO")
    assert ok.kind == "DISCONTINUOUS_JUMP" and ok.missing_intermediates == ["EC"]
    same = g.check_continuity("cell", "2026-09-16", "2026-09-17", "DC", "DC")
    assert same.kind == "CONTINUOUS" and same.missing_intermediates == []
    series = g.continuity_series("c", [("d1", "DC"), ("d2", "EC"), ("d3", "PO")])
    assert [t.kind for t in series] == ["CONTINUOUS", "CONTINUOUS"]


def test_blind_spot_bands_expand_and_classify():
    last = box(0, 0, 1, 1)
    bands = g.blind_spot_bands(last, 48.0, CFG["flood"]["v_max_m_per_hr"])
    assert bands["radius_m"] == pytest.approx(48.0 * CFG["flood"]["v_max_m_per_hr"])
    from shapely.geometry import shape
    must, may = shape(bands["must_be"]), shape(bands["may_be"])
    assert may.contains(must) and may.area > must.area
    assets = [("near", "bridges", Point(0.5, 0.5)), ("far", "bridges", Point(50, 50))]
    inside, outside = g.classify_assets(may, assets)
    assert [a["id"] for a in inside] == ["near"] and [a["id"] for a in outside] == ["far"]
    assert inside[0]["rcc8"] in ("TPP", "NTPP", "PO", "EQ", "TPPi", "NTPPi")


def test_split_reaches_north_south_rule():
    extent = box(0, 0, 10, 10)
    ways = [box(4, 4, 6, 12), box(-5, 20, 5, 21), box(-5, -5, 5, -4)]
    reaches = g.split_reaches(ways, extent)
    assert reaches == {"upstream": [1], "neck": [0], "downstream": [2]}


def test_detector_a_hypotheses_before_data_and_dipole():
    rivals = g.predict_a_rivals(100.0, 100.0)
    assert {h.id for h in rivals} == {"free_drainage", "impoundment"}
    assert all(h.status == "OPEN" for h in rivals)
    v = g.judge_detector_a(rivals, 100.0, 100.0, 160.0, 40.0)
    assert v.triggered is True
    by_id = {h.id: h.status for h in v.hypotheses}
    assert by_id == {"free_drainage": "FALSIFIED", "impoundment": "SUPPORTED"}
    v2 = g.judge_detector_a(rivals, 100.0, 100.0, 150.0, 140.0)
    assert v2.triggered is False
    assert {h.id: h.status for h in v2.hypotheses}["impoundment"] == "FALSIFIED"
    v3 = g.judge_detector_a(rivals, 100.0, 100.0, 100.0, 100.0)
    assert all(h.status == "OPEN" for h in v3.hypotheses)


def _dets(days_cells):
    return [(d, c) for d, cells in days_cells for c in cells]


def test_detector_b_falsification_and_rivals():
    claim = {"id": "cessation_claim", "start": "2026-09-20", "end": "2026-09-22"}
    dets = _dets([("2026-09-18", ["10.0,0.0"]), ("2026-09-20", ["10.0,0.0"]),
                  ("2026-09-21", ["10.1,0.0"])])
    v = g.detector_b(dets, claim, CFG)
    by_id = {h.id: h.status for h in v.hypotheses}
    assert by_id["cessation_claim"] == "FALSIFIED"
    assert by_id["smoldering"] == "SUPPORTED" and by_id["boundary_hopping"] == "SUPPORTED"
    assert by_id["extinction"] == "FALSIFIED"
    clean = g.detector_b(_dets([("2026-09-18", ["10.0,0.0"])]), claim, CFG)
    by_clean = {h.id: h.status for h in clean.hypotheses}
    assert by_clean["cessation_claim"] == "SUPPORTED" and by_clean["extinction"] == "SUPPORTED"


def test_detector_b_evasion_connected_vs_single():
    claim = {"id": "cessation_claim", "start": "2026-09-20", "end": "2026-09-22"}
    px = CFG["fire"]["viirs_pixel_area_ha"]
    per = CFG["fire"]["evasion_ha_per_cell"]
    n_each = int(per // px) - 1  # safely below the per-cell cap
    assert 2 * n_each * px > CFG["fire"]["evasion_ha_total"]  # but jointly over total
    spread = [(f"2026-09-19", "10.0,0.0")] * n_each + [(f"2026-09-19", "10.1,0.0")] * n_each
    v = g.detector_b(spread, claim, CFG)
    assert v.triggered is True
    assert {h.id: h.status for h in v.hypotheses}["evasion"] == "SUPPORTED"
    lumped = [(f"2026-09-19", "10.0,0.0")] * (2 * n_each)
    v2 = g.detector_b(lumped, claim, CFG)
    assert v2.triggered is False
