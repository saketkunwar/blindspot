"""BlindSpot study store (P1 persistence): SQLite over `store/schema.sql`.

Typed records for studies, runs, cassettes (as artifacts), and audit
trails. Every artifact is content-hashed (SHA-256); `verify_artifact`
recomputes the hash from the repo file. The module exposes INSERTs and
SELECTs only — runs are immutable and the audit trail is append-only
because no update or delete function exists.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib
import sqlite3

SCHEMA = pathlib.Path(__file__).with_name("schema.sql").read_text()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def connect(path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def add_study(con: sqlite3.Connection, study_id: str, domain_id: str,
              frozen_at: str, meta: dict | None = None) -> None:
    con.execute("INSERT INTO studies(id, domain_id, frozen_at, meta) VALUES (?,?,?,?)",
                (study_id, domain_id, frozen_at, json.dumps(meta or {}, sort_keys=True)))


def add_artifact(con: sqlite3.Connection, study_id: str, kind: str,
                 path: pathlib.Path) -> str:
    digest = sha256_file(path)
    con.execute("INSERT INTO artifacts(study_id, kind, path, sha256, recorded_at)"
                " VALUES (?,?,?,?,?)",
                (study_id, kind, str(path), digest, _now()))
    return digest


def add_run(con: sqlite3.Connection, study_id: str, inputs_hash: str, rules_hash: str,
            model_id: str, cassette_hashes: list, brief_hash: str,
            operator: str = "") -> int:
    cur = con.execute(
        "INSERT INTO runs(study_id, inputs_hash, rules_hash, model_id,"
        " cassette_hashes, brief_hash, operator, started_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (study_id, inputs_hash, rules_hash, model_id,
         json.dumps(sorted(cassette_hashes)), brief_hash, operator, _now()))
    return cur.lastrowid


def audit(con: sqlite3.Connection, actor: str, action: str,
          detail: dict | None = None) -> int:
    cur = con.execute("INSERT INTO audit(at, actor, action, detail) VALUES (?,?,?,?)",
                      (_now(), actor, action, json.dumps(detail or {}, sort_keys=True)))
    return cur.lastrowid


def set_study_token(con: sqlite3.Connection, study_id: str, token: str) -> None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    con.execute("INSERT INTO study_tokens(study_id, token_hash) VALUES (?,?)"
                " ON CONFLICT(study_id) DO UPDATE SET token_hash=excluded.token_hash",
                (study_id, digest))


def study_token_hash(con: sqlite3.Connection, study_id: str) -> str | None:
    row = con.execute("SELECT token_hash FROM study_tokens WHERE study_id=?",
                      (study_id,)).fetchone()
    return row[0] if row else None


def get_study(con: sqlite3.Connection, study_id: str) -> dict | None:
    row = con.execute("SELECT id, domain_id, frozen_at, meta FROM studies WHERE id=?",
                      (study_id,)).fetchone()
    if not row:
        return None
    return {"id": row[0], "domain_id": row[1], "frozen_at": row[2],
            "meta": json.loads(row[3])}


def list_studies(con: sqlite3.Connection) -> list:
    return [{"id": r[0], "domain_id": r[1], "frozen_at": r[2]}
            for r in con.execute("SELECT id, domain_id, frozen_at FROM studies ORDER BY id")]


def artifacts_for(con: sqlite3.Connection, study_id: str) -> list:
    return [{"kind": r[0], "path": r[1], "sha256": r[2], "recorded_at": r[3]}
            for r in con.execute("SELECT kind, path, sha256, recorded_at FROM artifacts"
                                 " WHERE study_id=? ORDER BY rowid", (study_id,))]


def runs_for(con: sqlite3.Connection, study_id: str) -> list:
    cols = ("rowid", "inputs_hash", "rules_hash", "model_id",
            "cassette_hashes", "brief_hash", "operator", "started_at")
    out = []
    for r in con.execute("SELECT rowid, inputs_hash, rules_hash, model_id,"
                         " cassette_hashes, brief_hash, operator, started_at"
                         " FROM runs WHERE study_id=? ORDER BY rowid", (study_id,)):
        d = dict(zip(cols, r))
        d["cassette_hashes"] = json.loads(d["cassette_hashes"])
        out.append(d)
    return out


def verify_artifact(root: pathlib.Path, artifact: dict) -> tuple[bool, str]:
    """Recompute the file hash; (ok, actual). Root prefixes relative paths."""
    p = pathlib.Path(artifact["path"])
    if not p.is_absolute():
        p = pathlib.Path(root) / p
    if not p.is_file():
        return False, "missing"
    actual = sha256_file(p)
    return actual == artifact["sha256"], actual
