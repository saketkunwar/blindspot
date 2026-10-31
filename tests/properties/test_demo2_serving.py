"""Durable Demo-2 serving tests: snapshot shape, real numbers, honest states."""
import json
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ.setdefault("BLINDSPOT_ROOT", str(ROOT))

from api.server import app  # noqa: E402

client = TestClient(app)

FIRE = json.loads((ROOT / "api/demo2_data/fire.json").read_text())
NEPAL = json.loads((ROOT / "api/demo2_data/nepal.json").read_text())


def test_demo2_fire_serves_real_census():
    body = client.get("/api/demo2/fire-study").json()
    assert body["mode"] == "cached"
    d = body["data"]
    ms = d["memory_status"]
    assert (ms["episodes"], ms["labelled"], ms["scenes"]) == (60, 32, 14)
    assert ms["patterns"] == 26 and ms["best_labelled"] == 5
    assert ms["speaking"] is True  # 5 of 5: the bar met by new episodes
    assert len(d["episodes"]) == ms["episodes"]
    assert sum(1 for e in d["episodes"] if e["label"] != "unlabelable") == 32
    assert d["null_test"]["null_edge"] == -0.13
    assert d["null_test"]["signal_edge"] == 0.27
    assert d["hill_climb"]["candidates_filed"] == 0


def test_demo2_fire_validation_blocks():
    d = client.get("/api/demo2/fire-study").json()["data"]["validation"]
    assert d["temporal"]["match"] is True
    assert d["temporal"]["cutoff_day"] == "2026-09-20"
    s = d["spatial"]
    assert (s["kept"], s["total"]) == (3071, 6142)
    assert s["top"] == "suppression_then_restart"
    assert s["ranking_identical"] is True
    assert s["probabilities_identical"] is True


def test_demo2_nepal_validation_blocks():
    d = client.get("/api/demo2/nepal-cascade").json()["data"]["validation"]
    assert d["temporal"]["match"] is True
    assert d["temporal"]["newly_destroyed"] == 754
    assert d["temporal"]["frozen_top"] == "impoundment_then_burst"
    assert d["spatial"]["status"] == "pending"


def test_demo2_nepal_proves_identity_and_emptiness():
    body = client.get("/api/demo2/nepal-cascade").json()
    d = body["data"]
    assert d["memory_status"]["episodes"] == 0
    assert d["identity"]["match"] is True
    assert d["identity"]["frozen_brief_sha256"] == \
        d["identity"]["memory_empty_brief_sha256"]
    assert d["why_empty"]["dated_damage_days"] == 2
    assert d["why_empty"]["dateless_features"] == 8368
    assert len(d["unlock"]) == 3


def test_demo2_live_reading():
    d = client.get("/api/demo2/fire-study").json()["data"]["live"]
    assert d["as_of"] == "2026-10-30" and d["detections"] == 675
    assert d["study_window"] == ["2026-09-16", "2026-09-20"]
    assert "restart" in d["held_out"]
    assert sum(x["detections"] for x in d["days"]) == 675
    assert d["bbox_check"]["inside_study_box"] is True
    assert d["matches_frozen"] is True
    assert d["ranking"][0]["id"] == "suppression_then_restart"
    assert d["pattern_match"] == {"episodes": 6, "labelled": 4,
                                  "known": True}


def test_demo2_openapi_lists_both():
    spec = json.loads((ROOT / "api/openapi.json").read_text())
    assert "/api/demo2/fire-study" in spec["paths"]
    assert "/api/demo2/nepal-cascade" in spec["paths"]


def test_demo2_chain_forces_verdict():
    r = client.get("/api/demo2/nepal-chain")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["subject"] == "bridges:0" and len(d["hops"]) == 4
    assert d["composition"]["allowed"] == ["NTPP"]
    assert d["composition"]["match"] is True
    assert "skipped" in d["temporal"]


def test_demo2_cross_region_standings():
    r = client.get("/api/demo2/cross-region")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["episodes"] >= 48 and d["patterns"] >= 22
    assert d["cross_scene"] >= 9
    lead = d["top_patterns"][0]
    assert lead["labelled"] >= 4
    assert "iberia_ext" in d["pending_pulls"]
    assert sum(s["episodes"] for s in d["scenes"]) == d["episodes"]


def test_demo2_cross_region_regenerates_identically(tmp_path):
    import hashlib
    import subprocess
    import sys
    before = hashlib.sha256(
        (ROOT / "api/demo2_data/crossregion.json").read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, "scripts/make_crossregion.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0
    after = hashlib.sha256(
        (ROOT / "api/demo2_data/crossregion.json").read_bytes()).hexdigest()
    assert before == after


def test_demo2_morning_run_narrates_steps():
    r = client.post("/api/demo2/morning-run")
    assert r.status_code == 200
    body = r.json()
    assert body["demo"] is True and body["as_of"] == "2026-10-30"
    names = [s["name"] for s in body["steps"]]
    assert names == ["pull", "score", "memory", "decide", "snippet"]
    mem = body["steps"][2]
    assert mem["labelled"] == 4 and mem["speak_bar"] == 5
    assert mem["speaks"] is False
    assert body["trigger"] == "spike"
    assert body["snippet"].startswith("2026-10-30: 150 detections")
