"""Durable P3 operations tests: status tables, health shape, log discipline.

Table functions run against the real seeded store (read-only); the
status exit path runs against an empty fixture (fast-fail). Health is
exercised through the API test client (no recompute).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import status as _status


def test_status_tables_cover_both_studies():
    studies = {r[0]: r for r in _status.studies_table(ROOT)}
    assert {"nepal-cascade", "kalimantan-fire"} <= set(studies)
    for sid, row in studies.items():
        ok, total = row[3].split("/")
        assert ok == total and int(total) > 0, (sid, row)
    runs = _status.runs_table(ROOT)
    assert {r[0] for r in runs} >= {"nepal-cascade", "kalimantan-fire"}
    usage = _status.usage_table(ROOT)
    assert usage, "model usage table empty"
    assert sum(int(r[1]) for r in usage) > 0


def test_status_exits_nonzero_without_store(tmp_path):
    rc = _status.main(["--root", str(tmp_path)])
    assert rc == 1


def test_health_reports_per_study_status():
    from fastapi.testclient import TestClient
    import api.server as _srv
    client = TestClient(_srv.app)
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/health/detail").json()
    assert body["status"] == "ok", body
    assert body["store"] == "seeded"
    assert body["studies"]["nepal-cascade"]["brief"] == "ok"
    assert body["studies"]["kalimantan-fire"]["brief"] == "ok"
    assert body["studies"]["nepal-cascade"]["top"] == "impoundment_then_burst"
    assert body["studies"]["kalimantan-fire"]["top"] == "suppression_then_restart"


def test_ops_log_lines_are_json():
    import io
    import logging
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("blindspot.api")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        from api import server as _srv
        _srv._ops_log("test.ping", study="x", mode="cached")
    finally:
        logger.removeHandler(handler)
    line = stream.getvalue().strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["action"] == "test.ping" and entry["study"] == "x"
