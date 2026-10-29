"""Durable P1 auth tests: operator token for live mode, per-study read tokens.

Policy under test (see `api/server.py`): live recompute needs the operator
token, but only when one is configured (unset = dev-open, so the keyless
replay path and the pre-existing suite keep working). Per-study read tokens
live hashed in the store and are enforced whenever set; the operator token
always bypasses. Nothing here invents tokens: values are test-only.
"""
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ.setdefault("BLINDSPOT_ROOT", str(ROOT))

from scripts import seed_store  # noqa: E402
from store import db  # noqa: E402

import api.server as srv  # noqa: E402

client = TestClient(srv.app)
STUDY = "nepal-cascade"


@pytest.fixture()
def operator(monkeypatch):
    monkeypatch.setenv("BLINDSPOT_OPERATOR_TOKEN", "op-token")
    yield "op-token"


@pytest.fixture()
def tokened_store(tmp_path, monkeypatch):
    out = tmp_path / "store.sqlite3"
    seed_store.seed(ROOT, out)
    con = db.connect(out)
    db.set_study_token(con, STUDY, "study-token")
    con.commit()
    con.close()
    monkeypatch.setenv("BLINDSPOT_STORE", str(out))
    return out


def test_dev_open_without_operator_token():
    os.environ.pop("BLINDSPOT_OPERATOR_TOKEN", None)
    assert client.get(f"/v1/studies/{STUDY}/brief").status_code == 200


def test_live_needs_operator_token_when_configured(operator):
    assert client.get(f"/v1/studies/{STUDY}/gt?mode=live").status_code == 401
    r = client.get(f"/v1/studies/{STUDY}/gt?mode=live",
                   headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    r = client.get(f"/v1/studies/{STUDY}/gt?mode=live",
                   headers={"Authorization": f"Bearer {operator}"})
    assert r.status_code == 200 and r.json()["mode"] == "live"


def test_cached_reads_ignore_operator_token(operator):
    assert client.get(f"/v1/studies/{STUDY}/brief").status_code == 200


def test_study_token_gates_reads(tokened_store):
    os.environ.pop("BLINDSPOT_OPERATOR_TOKEN", None)
    assert client.get(f"/v1/studies/{STUDY}/brief").status_code == 401
    assert client.get(f"/v1/studies/{STUDY}/geo").status_code == 401
    r = client.get(f"/v1/studies/{STUDY}/brief",
                   headers={"Authorization": "Bearer study-token"})
    assert r.status_code == 200 and r.json()["mode"] == "cached"


def test_operator_bypasses_study_token(tokened_store, operator):
    r = client.get(f"/v1/studies/{STUDY}/geo",
                   headers={"Authorization": f"Bearer {operator}"})
    assert r.status_code == 200
