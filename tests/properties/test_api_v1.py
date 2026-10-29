"""Durable P1 API-contract tests: versioned study reads over frozen artifacts.

Pins `/v1/studies`, `/{id}/brief`, `/{id}/geo`, `/{id}/gt`: mode labels,
frozen-artifact shapes, honest 404/400 states, legacy-alias parity, live
determinism, and `api/openapi.json` sync with the routes. No seeded data:
every expectation is read off the committed artifacts at test time.
"""
import hashlib
import json
import os
import pathlib

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ.setdefault("BLINDSPOT_ROOT", str(ROOT))

from api.server import app  # noqa: E402

client = TestClient(app)
STUDY = "nepal-cascade"


def test_studies_list_and_unknown_id():
    body = client.get("/v1/studies").json()
    assert {"id": STUDY} in body["studies"]
    assert client.get("/v1/studies/no-such-study/brief").status_code == 404
    assert client.get("/v1/studies/no-such-study/geo").status_code == 404
    assert client.get("/v1/studies/no-such-study/gt").status_code == 404


def test_brief_cached_shape_and_bad_mode():
    r = client.get(f"/v1/studies/{STUDY}/brief")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "cached"
    assert body["data"]["mechanisms"][0]["id"]
    assert "ledger" in body["data"]
    assert client.get(f"/v1/studies/{STUDY}/brief?mode=stale").status_code == 400


def test_brief_live_parity_of_ranking():
    live = client.get(f"/v1/studies/{STUDY}/brief?mode=live").json()
    cached = client.get(f"/v1/studies/{STUDY}/brief").json()["data"]
    assert live["mode"] == "live"
    assert [m["id"] for m in live["data"]["mechanisms"]] == [m["id"] for m in cached["mechanisms"]]


def test_legacy_brief_and_geo_aliases_identical():
    assert client.get("/api/demo/nepal-cascade").json() == client.get(
        f"/v1/studies/{STUDY}/brief").json()
    assert client.get("/api/demo/nepal-cascade/geo").json() == client.get(
        f"/v1/studies/{STUDY}/geo").json()


def test_geo_layers_and_cap():
    body = client.get(f"/v1/studies/{STUDY}/geo").json()
    assert body["mode"] == "cached"
    data = body["data"]
    assert data["sample_cap"] == 500
    assert data["pre_cutoff_total"] >= len(data["layers"]) - 2  # reach + outline box
    kinds = {f["properties"]["kind"] for f in data["layers"]}
    assert {"target reach", "observed flood outline", "pre-cutoff damage"} <= kinds


def test_gt_cached_and_live_deterministic():
    gt_path = ROOT / "demo" / "nepal_cascade" / "output" / "gt_check.json"
    before = hashlib.sha256(gt_path.read_bytes()).hexdigest()
    cached = client.get(f"/v1/studies/{STUDY}/gt").json()
    assert cached["mode"] == "cached"
    assert cached["data"]["verdict"] and cached["data"]["frozen_top_mechanism"]
    live = client.get(f"/v1/studies/{STUDY}/gt?mode=live").json()
    assert live["mode"] == "live"
    assert live["data"] == cached["data"]
    assert hashlib.sha256(gt_path.read_bytes()).hexdigest() == before
    assert client.get(f"/v1/studies/{STUDY}/gt?mode=stale").status_code == 400


def test_openapi_schema_in_sync():
    from api.server import app as _app
    fresh = json.dumps(_app.openapi(), indent=1, sort_keys=True) + "\n"
    committed = (ROOT / "api" / "openapi.json").read_text()
    assert committed == fresh
    paths = json.loads(committed)["paths"]
    for p in ("/v1/studies", "/v1/studies/{study_id}/brief",
              "/v1/studies/{study_id}/geo", "/v1/studies/{study_id}/gt"):
        assert p in paths
