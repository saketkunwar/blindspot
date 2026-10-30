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
    assert (ms["episodes"], ms["labelled"], ms["scenes"]) == (48, 26, 11)
    assert ms["patterns"] == 22 and ms["best_labelled"] == 4
    assert ms["speaking"] is False  # 4 of 5: silence, verified not promised
    assert len(d["episodes"]) == ms["episodes"]
    assert sum(1 for e in d["episodes"] if e["label"] != "unlabelable") == 26
    assert d["null_test"]["null_edge"] == -0.13
    assert d["null_test"]["signal_edge"] == 0.27
    assert d["hill_climb"]["candidates_filed"] == 0


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


def test_demo2_openapi_lists_both():
    spec = json.loads((ROOT / "api/openapi.json").read_text())
    assert "/api/demo2/fire-study" in spec["paths"]
    assert "/api/demo2/nepal-cascade" in spec["paths"]
