"""Durable Phase-4 meta-stack tests. Fail-closed on invented or unverified content."""
import json
import pathlib

import pytest
from shapely.geometry import box

from agents import muse_abductor as ab
from agents import sam_perception as sam
from agents import verification_gate as vg
from agents.ledger import build_ledger

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _req(image="chip", prompt="extent"):
    return {"image": image, "prompt": prompt, "model": sam.MODEL}


def test_perceive_cassette_hit_cache_and_log(tmp_path):
    cas, cache, usage = tmp_path / "cas", tmp_path / "cache", tmp_path / "usage.json"
    cas.mkdir()
    poly = box(0, 0, 1, 1).__geo_interface__
    (cas / f"{sam.canonical_hash(_req())}.json").write_text(
        json.dumps({"request": _req(), "response": {"masks": [poly]}}) + "\n")
    geoms = sam.perceive("chip", "extent", cassettes_dir=cas, cache_dir=cache, usage_path=usage)
    assert len(geoms) == 1 and geoms[0].is_valid and geoms[0].area == pytest.approx(1.0)
    geoms2 = sam.perceive("chip", "extent", cassettes_dir=cas, cache_dir=cache, usage_path=usage)
    assert geoms2[0].equals(geoms[0])
    log = json.loads(usage.read_text())
    assert [e["source"] for e in log] == ["cassette", "cache"]
    assert all(e["request_hash"] == sam.canonical_hash(_req()) and "ts" in e for e in log)


def test_perceive_miss_raises_and_logs(tmp_path):
    cas, cache, usage = tmp_path / "c", tmp_path / "k", tmp_path / "u.json"
    cas.mkdir()
    with pytest.raises(sam.CassetteMiss):
        sam.perceive("nope", "nothing", cassettes_dir=cas, cache_dir=cache, usage_path=usage)
    assert json.loads(usage.read_text())[0]["hit"] is False


def test_seed_cassettes_loadable():
    seeds = sorted((ROOT / "data/cassettes").glob("*.json"))
    assert seeds, "at least one seed cassette must ship"
    for s in seeds:
        saved = json.loads(s.read_text())
        assert s.name == f"{sam.canonical_hash(saved['request'])}.json"
        assert all(m["type"] in ("Polygon", "MultiPolygon") for m in saved["response"]["masks"])


def test_abductor_roles_schema_validated():
    claims = ab.extract_claims("Bridge 7 is DC, 14.0 m from the flood.", source="pitch")
    assert claims and claims[0].relations == ["DC"] and claims[0].numbers == [7.0, 14.0]
    # extractor harvests; the gate decides what is ledger-true
    rivals = ab.write_rivals("cessation_claim", "fire_kalimantan")
    assert rivals.rivals == ["extinction", "smoldering", "boundary_hopping", "evasion"]
    brief = ab.write_brief("t", [{"text": "x is DC.", "relations": ["DC"]}])
    assert isinstance(brief, ab.Brief) and brief.statements[0].relations == ["DC"]
    with pytest.raises(Exception):
        ab.Statement(text="x", relations=["DC"], bogus_field=1)


def _ledger():
    flood = {"scenario": "flood_nepal",
             "act1": {"features": [{"id": "bridges:7", "layer": "bridges",
                                    "fwd": {"rcc8": {"relation": "DC"},
                                            "rectangle": ["di", "di"]}}]}}
    fire = {"scenario": "fire_kalimantan",
            "cells": [{"id": "10.0,0.0", "counts": {"2026-09-20": 9},
                       "rcc8": {"2026-09-20": "NTPP"}}],
            "timeline_relations": [{"a": "x", "b": "y", "relation": "m"}],
            "claims": [{"id": "cessation_claim"}]}
    return build_ledger(flood, fire, {"site": "Kalimantan"})


def test_gate_passes_verified_strips_rest():
    ledger = _ledger()
    good = ab.Statement(text="bridges:7 is DC.", entities=["bridges:7"], relations=["DC"])
    bad = ab.Statement(text="Unit 5 shows EQ at 99 m.", entities=["bridges:9"],
                       relations=["NTPP"], numbers=[99.0])
    ok, brief, viols = vg.check(ab.Brief(title="t", statements=[good, bad]), ledger, mode="strip")
    assert ok and len(brief.statements) == 1 and len(viols) == 4
    ok2, out2, _ = vg.check(ab.Brief(title="t", statements=[good, bad]), ledger, mode="block")
    assert ok2 is False and out2 is None


def test_gate_empty_ledger_gives_number_free_brief():
    ledger = {"relations": set(), "numbers": [], "entities": set()}
    st = ab.Statement(text="gap 12.5 m.", numbers=[12.5])
    ok, brief, _ = vg.check(ab.Brief(title="t", statements=[st]), ledger, mode="strip")
    assert ok and brief.statements == []
