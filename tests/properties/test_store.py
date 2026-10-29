"""Durable P1 persistence tests: seed determinism, hash verification, append-only shape."""
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import seed_store  # noqa: E402
from store import db  # noqa: E402


def _seed(tmp_path, name="store.sqlite3"):
    out = tmp_path / name
    summary = seed_store.seed(ROOT, out)
    return out, summary


def test_seed_records_study_artifacts_run_and_audit(tmp_path):
    out, summary = _seed(tmp_path)
    con = db.connect(out)
    study = db.get_study(con, "nepal-cascade")
    assert study and study["domain_id"] == "river_valley_flood"
    kinds = {a["kind"] for a in db.artifacts_for(con, "nepal-cascade")}
    assert {"brief", "gt", "rules", "inputs-audit"} <= kinds
    assert len(db.runs_for(con, "nepal-cascade")) == 1
    assert summary["artifacts"]
    fire = db.get_study(con, "kalimantan-fire")
    fdomain = json.loads((ROOT / "demo/fire_study/domain.json").read_text())
    assert fire and fire["domain_id"] == fdomain["domain_id"]
    fkinds = {a["kind"] for a in db.artifacts_for(con, "kalimantan-fire")}
    assert {"brief", "rules", "inputs-audit", "card"} <= fkinds
    assert len(db.runs_for(con, "kalimantan-fire")) == 1
    for run in db.runs_for(con, "nepal-cascade") + db.runs_for(con, "kalimantan-fire"):
        assert "None" not in run["cassette_hashes"], "null request hash leaked as cassette"
    con.close()


def test_all_artifacts_verify_against_repo_files(tmp_path):
    out, _ = _seed(tmp_path)
    con = db.connect(out)
    for art in db.artifacts_for(con, "nepal-cascade"):
        ok, _ = db.verify_artifact(ROOT, art)
        assert ok, art
    con.close()


def test_reseed_is_deterministic(tmp_path):
    _, first = _seed(tmp_path, "a.sqlite3")
    _, second = _seed(tmp_path, "b.sqlite3")
    assert first["artifacts"] == second["artifacts"]


def test_tampered_copy_fails_verification(tmp_path):
    out, _ = _seed(tmp_path)
    src = ROOT / "demo" / "nepal_cascade" / "output" / "brief.json"
    copy = tmp_path / "brief_copy.json"
    copy.write_bytes(src.read_bytes())
    con = db.connect(out)
    db.add_artifact(con, "nepal-cascade", "probe-copy", copy)
    art = db.artifacts_for(con, "nepal-cascade")[-1]
    ok, _ = db.verify_artifact(ROOT, art)
    assert ok
    copy.write_text(copy.read_text() + " ")
    ok, _ = db.verify_artifact(ROOT, art)
    assert not ok
    con.close()


def test_no_update_or_delete_path():
    exposed = [n for n in dir(db) if "update" in n or "delete" in n or "drop" in n]
    assert exposed == []
    con = sqlite3.connect(":memory:")
    con.executescript(db.SCHEMA)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"studies", "artifacts", "runs", "audit", "study_tokens"} <= tables
    con.close()


def test_audit_appends_in_order(tmp_path):
    out, _ = _seed(tmp_path)
    con = db.connect(out)
    first = db.audit(con, "probe", "one")
    second = db.audit(con, "probe", "two")
    assert second > first
    con.close()
