"""Durable Phase-5 serving tests: mode labels, cached/live parity of shape, honest missing states."""
import json
import os
import pathlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ.setdefault("BLINDSPOT_ROOT", str(ROOT))

from api.server import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _results_present():
    for name, mod in (("flood", "pipelines.flood_secondary_dam"),
                      ("fire", "pipelines.fire_peat_evasion")):
        p = ROOT / "results" / f"{name}.json"
        if not p.exists():
            r = subprocess.run([sys.executable, "-m", mod, "--data-dir", "data", "--out", str(p)],
                               cwd=ROOT, capture_output=True, text=True, timeout=900)
            assert r.returncode == 0, r.stderr[-500:]


def test_health_and_index():
    assert client.get("/health").json() == {"status": "ok"}
    assert "endpoints" in client.get("/").json()


def test_cached_results_labelled_and_shaped():
    for name, scenario in (("flood", "flood_nepal"), ("fire", "fire_kalimantan")):
        r = client.get(f"/api/results/{name}")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "cached" and body["data"]["scenario"] == scenario
    assert "act1" in client.get("/api/results/flood").json()["data"]
    assert "cells" in client.get("/api/results/fire").json()["data"]


def test_live_flood_matches_cached_shape():
    body = client.get("/api/results/flood?mode=live").json()
    assert body["mode"] == "live"
    cached = client.get("/api/results/flood").json()["data"]
    assert [f["id"] for f in body["data"]["act1"]["features"]] == [f["id"] for f in cached["act1"]["features"]]
    assert body["data"]["act3"]["status"] == cached["act3"]["status"]


def test_bad_mode_rejected_and_evidence_honest():
    assert client.get("/api/results/flood?mode=stale").status_code == 400
    r = client.get("/api/evidence")
    if not (ROOT / "results" / "evidence.json").exists():
        assert r.status_code == 404
    else:
        assert r.json()["mode"] == "cached"


def test_flood_assets_cover_act1_ids():
    r = client.get("/api/results/flood/assets")
    assert r.status_code == 200
    by_id = {a["id"]: a["geometry"] for a in r.json()["assets"]}
    cached = client.get("/api/results/flood").json()["data"]
    ids = [f["id"] for f in cached["act1"]["features"]]
    assert len(ids) == 195 and set(ids) <= set(by_id)
    assert all(isinstance(g, dict) and g.get("type") for g in by_id.values())
    assert by_id["flood-extent"]["type"] == "Polygon"
