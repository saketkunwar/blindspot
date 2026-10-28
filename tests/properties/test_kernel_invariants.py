"""Durable Phase-1 kernel invariants. Fail-closed: any red means the kernel is wrong."""
import json
import pathlib

import pytest
from shapely.geometry import Point, box

import engine.qstr_core as q
import engine.propagation as p
from engine.neighborhood import NEIGHBORS, shortest_path
from engine.schemas import ConfigIncomplete, Snapshot, load_preregistered

ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = load_preregistered(ROOT / "config/preregistered.yaml")


# ------------------------------------------------------------- Allen (T-1.4)
def test_allen_endpoints_meet_not_before():
    assert q.allen("2026-09-16", "2026-09-17", "2026-09-17", "2026-09-21") == "m"


def test_allen_all_thirteen():
    cases = [
        ((0, 1), (2, 3), "b"), ((0, 1), (1, 2), "m"), ((0, 2), (1, 3), "o"),
        ((0, 1), (0, 2), "s"), ((1, 2), (0, 3), "d"), ((1, 2), (0, 2), "f"),
        ((0, 1), (0, 1), "eq"), ((0, 2), (0, 1), "si"), ((0, 3), (1, 2), "di"),
        ((0, 2), (1, 2), "fi"), ((1, 3), (0, 2), "oi"), ((1, 2), (0, 1), "mi"),
        ((2, 3), (0, 1), "bi"),
    ]
    assert len({c for _, _, c in cases}) == 13
    for (a0, a1), (b0, b1), want in cases:
        assert q.allen(a0, a1, b0, b1) == want
        assert q.allen(b0, b1, a0, a1) == q.ALLEN_INVERSE[want]


def test_allen_composition_exact():
    assert q.ALLEN_COMPOSITION["b"]["b"] == frozenset({"b"})
    assert q.ALLEN_COMPOSITION["m"]["m"] == frozenset({"b"})
    for r in q.ALLEN_RELATIONS:
        assert q.ALLEN_COMPOSITION["eq"][r] == frozenset({r})
        assert q.ALLEN_COMPOSITION[r]["eq"] == frozenset({r})
        for c in q.ALLEN_RELATIONS:
            assert len(q.ALLEN_COMPOSITION[r][c]) > 0
            conv = {q.ALLEN_INVERSE[x] for x in q.ALLEN_COMPOSITION[c][r]}
            assert q.ALLEN_COMPOSITION[q.ALLEN_INVERSE[r]][q.ALLEN_INVERSE[c]] == frozenset(conv)


# -------------------------------------------------------------- RCC-8 (T-1.2)
def _shapes():
    big = box(0, 0, 10, 10)
    return {
        "DC": (box(20, 20, 21, 21), big),
        "EC": (box(10, 0, 12, 10), big),
        "PO": (box(5, 5, 15, 15), big),
        "EQ": (box(0, 0, 10, 10), big),
        "TPP": (box(0, 0, 5, 5), big),
        "NTPP": (box(2, 2, 5, 5), big),
        "TPPi": (big, box(0, 0, 5, 5)),
        "NTPPi": (big, box(2, 2, 5, 5)),
    }


def test_rcc8_all_eight_and_inverse():
    for want, (a, b) in _shapes().items():
        assert q.rcc8(a, b) == want, want
        assert q.rcc8(b, a) == q.RCC8_INVERSE[want], want


def test_rcc8_table_verified_properties():
    assert p.RCC8_COMPOSITION["TPP"]["EC"] == frozenset({"DC", "EC"})
    for r in q.RCC8_RELATIONS:
        assert p.RCC8_COMPOSITION["EQ"][r] == frozenset({r})
        assert p.RCC8_COMPOSITION[r]["EQ"] == frozenset({r})
        for c in q.RCC8_RELATIONS:
            assert len(p.RCC8_COMPOSITION[r][c]) > 0
            conv = {q.RCC8_INVERSE[x] for x in p.RCC8_COMPOSITION[c][r]}
            assert p.RCC8_COMPOSITION[q.RCC8_INVERSE[r]][q.RCC8_INVERSE[c]] == frozenset(conv)


def test_path_consistency_refines_and_contradicts():
    nodes = ["a", "b", "c"]
    cons = {frozenset(("a", "b")): {"TPP"}, frozenset(("b", "c")): {"EC"}}
    refined, bad = p.path_consistency(nodes, cons)
    assert not bad and refined[("a", "c")] == {"DC", "EC"}
    assert refined[("c", "a")] == {"DC", "EC"}
    assert p.network_status(refined)[("a", "c")] == "POSSIBLE"
    cons2 = {frozenset(("a", "b")): {"DC"}, frozenset(("b", "c")): {"EQ"},
             frozenset(("a", "c")): {"PO"}}
    _, bad2 = p.path_consistency(nodes, cons2)
    assert bad2


# ------------------------------------------------- Rectangle / tiles (T-1.4/5)
def test_rectangle_and_snapshot_inverse():
    small, big = box(2, 2, 5, 5), box(0, 0, 10, 10)
    fwd, inv = q.snapshot_pair(small, big, CFG)
    Snapshot(**fwd)
    Snapshot(**inv)
    assert fwd["rcc8"]["relation"] == "NTPP" and inv["rcc8"]["relation"] == "NTPPi"
    assert fwd["rectangle"] == ["d", "d"] and inv["rectangle"] == ["di", "di"]
    assert set(inv["tiles"]) == set(q.TILES)  # flood seen from an inside bridge: all nine


def test_tiles_and_bearing_cardinal():
    ref = box(0, 0, 10, 10)
    assert q.tiles_of(box(20, 20, 21, 21).bounds, ref.bounds) == ["NE"]
    assert q.tiles_of(box(-5, -5, -1, -1).bounds, ref.bounds) == ["SW"]
    assert q.bearing_word((20, 5), (5, 5)) == "E"
    assert q.bearing_word((5, 5), (5, 5)) == "O"


# --------------------------------------------------------- Distance (T-1.6)
def _east_of(origin, meters: float):
    import math
    dlon = meters / (111320.0 * math.cos(math.radians(origin.y)))
    return Point(origin.x + dlon, origin.y)


def test_bands_from_config_thresholds():
    env = CFG["distance"]["immediate_envelope_m"]
    origin = Point(84.0, 27.0)
    assert q.band_for(q.edge_gap_m(origin, origin), CFG) == "CONTACT"
    assert q.band_for(q.edge_gap_m(origin, _east_of(origin, env / 2)), CFG) == "IMMEDIATE_ENVELOPE"
    assert q.band_for(q.edge_gap_m(origin, _east_of(origin, 2000.0)), CFG) == "NEAR"
    assert q.band_for(q.edge_gap_m(origin, _east_of(origin, 10000.0)), CFG) == "MEDIUM"
    assert q.band_for(q.edge_gap_m(origin, _east_of(origin, 100000.0)), CFG) == "FAR"
    assert q.centroid_dist_km(origin, _east_of(origin, 1000.0)) == pytest.approx(1.0, rel=0.05)


# ------------------------------------------------------- Neighborhood (T-1.7)
def test_neighborhood_textbook_present_teleports_absent():
    for a, b in [("DC", "EC"), ("EC", "PO"), ("PO", "TPP"), ("PO", "TPPi"),
                 ("TPP", "NTPP"), ("TPPi", "NTPPi"), ("TPP", "EQ"), ("TPPi", "EQ")]:
        assert b in NEIGHBORS[a] and a in NEIGHBORS[b]
    for a, b in [("DC", "PO"), ("PO", "DC"), ("DC", "NTPP"), ("NTPP", "DC"),
                 ("DC", "NTPPi"), ("NTPPi", "DC"), ("DC", "EQ"), ("EQ", "DC"),
                 ("PO", "NTPP"), ("NTPP", "PO"), ("EC", "NTPP"), ("NTPP", "EC")]:
        assert b not in NEIGHBORS[a], (a, b)
    assert shortest_path("DC", "PO") == ["EC"]
    assert shortest_path("NTPP", "DC") == ["TPP", "PO", "EC"]


# ------------------------------------------------------- Real-data grounding
def _load_features(path):
    feats = json.loads(pathlib.Path(path).read_text())["features"]
    from shapely.geometry import shape
    return [shape(f["geometry"]) for f in feats if f.get("geometry")]


def test_kernel_on_real_flood_data():
    flood = _load_features(ROOT / "data/flood_nepal/flood_extent.geojson")[0]
    n = 0
    for name in ("bridges", "hydropowers", "helipads"):
        for g in _load_features(ROOT / f"data/flood_nepal/{name}.geojson"):
            fwd, inv = q.snapshot_pair(g, flood, CFG)
            Snapshot(**fwd)
            Snapshot(**inv)
            assert inv["rcc8"]["relation"] == q.RCC8_INVERSE[fwd["rcc8"]["relation"]]
            assert inv["edge_gap_m"] == pytest.approx(fwd["edge_gap_m"])
            assert set(inv["tiles"]).issubset(set(q.TILES)) and fwd["band"] in (
                "CONTACT", "IMMEDIATE_ENVELOPE", "NEAR", "MEDIUM", "FAR")
            n += 1
    assert n > 100


def test_config_fail_closed(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("tolerance:\n  ingest_deg: null\n")
    with pytest.raises(ConfigIncomplete):
        load_preregistered(bad)
