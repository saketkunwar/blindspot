"""Durable P1 presentation tests: server-rendered study page, data-only."""
import json
import os
import pathlib
import sys

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ.setdefault("BLINDSPOT_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT))

from api.server import app  # noqa: E402

client = TestClient(app)
STUDY = "nepal-cascade"


def _brief():
    return json.loads((ROOT / "demo" / "nepal_cascade" / "output" / "brief.json").read_text())


def test_page_renders_frozen_content_only():
    r = client.get(f"/v1/studies/{STUDY}/page")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    brief = _brief()
    top = brief["mechanisms"][0]
    assert top["id"] in body and ("%.4f" % top["probability"]) in body
    for fid in brief["ledger"]["facts"]:
        assert fid in body
    for m in brief["mechanisms"]:
        assert m["id"] in body
    assert "@media print" in body and "<svg" in body


def test_page_unknown_study_404():
    assert client.get("/v1/studies/no-such-study/page").status_code == 404


def test_page_in_openapi():
    from api.server import app as _app
    assert "/v1/studies/{study_id}/page" in _app.openapi()["paths"]


def test_browser_cross_origin_reads_allowed():
    r = client.get(f"/v1/studies/{STUDY}/brief",
                   headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "*"
    pre = client.options(f"/v1/studies/{STUDY}/brief",
                         headers={"Origin": "http://localhost:3000",
                                  "Access-Control-Request-Method": "GET"})
    assert pre.status_code == 200
    pre_post = client.options("/api/demo2/morning-run",
                              headers={"Origin": "http://localhost:3000",
                                       "Access-Control-Request-Method": "POST"})
    assert pre_post.status_code == 200
