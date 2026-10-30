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


def add_episode(con: sqlite3.Connection, episode_id: str, scene: str,
                scene_sha256: str, cutoff: str, n_pre: int,
                days_pre: list, cells_pre: int, facts: dict,
                ranking: list, top_mechanism: str) -> None:
    """Insert one rolling-origin episode. Insert-only: reruns of the same
    episode id raise IntegrityError instead of overwriting."""
    con.execute("INSERT INTO episodes(episode_id, scene, scene_sha256, cutoff,"
                " n_pre, days_pre, cells_pre, facts_json, ranking_json,"
                " top_mechanism, recorded_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (episode_id, scene, scene_sha256, cutoff, n_pre,
                 json.dumps(sorted(days_pre)), cells_pre,
                 json.dumps(facts, sort_keys=True),
                 json.dumps(ranking, sort_keys=True),
                 top_mechanism, _now()))


def add_outcome(con: sqlite3.Connection, episode_id: str, rule_id: str,
                lookahead_days: int, window_start: str, window_end: str,
                n_post: int, label: str) -> int:
    cur = con.execute("INSERT INTO outcomes(episode_id, rule_id, lookahead_days,"
                      " window_start, window_end, n_post, label, recorded_at)"
                      " VALUES (?,?,?,?,?,?,?,?)",
                      (episode_id, rule_id, lookahead_days, window_start,
                       window_end, n_post, label, _now()))
    return cur.lastrowid


def episodes_for(con: sqlite3.Connection, scene: str | None = None) -> list:
    q = ("SELECT episode_id, scene, scene_sha256, cutoff, n_pre, days_pre,"
         " cells_pre, facts_json, ranking_json, top_mechanism, recorded_at"
         " FROM episodes")
    args: tuple = ()
    if scene is not None:
        q += " WHERE scene=?"
        args = (scene,)
    q += " ORDER BY scene, cutoff"
    out = []
    for r in con.execute(q, args):
        out.append({"episode_id": r[0], "scene": r[1], "scene_sha256": r[2],
                    "cutoff": r[3], "n_pre": r[4],
                    "days_pre": json.loads(r[5]), "cells_pre": r[6],
                    "facts": json.loads(r[7]), "ranking": json.loads(r[8]),
                    "top_mechanism": r[9], "recorded_at": r[10]})
    return out


def outcomes_for(con: sqlite3.Connection, episode_id: str | None = None) -> list:
    cols = ("rowid", "episode_id", "rule_id", "lookahead_days",
            "window_start", "window_end", "n_post", "label", "recorded_at")
    q = ("SELECT rowid, episode_id, rule_id, lookahead_days, window_start,"
         " window_end, n_post, label, recorded_at FROM outcomes")
    args: tuple = ()
    if episode_id is not None:
        q += " WHERE episode_id=?"
        args = (episode_id,)
    q += " ORDER BY episode_id, rowid"
    return [dict(zip(cols, r)) for r in con.execute(q, args)]


def census(con: sqlite3.Connection) -> list:
    """One row per episode with its outcome label (if any), ordered for
    stable census tables. Timestamps are excluded so reruns compare equal."""
    rows = con.execute(
        "SELECT e.episode_id, e.scene, e.cutoff, e.n_pre, e.cells_pre,"
        " e.top_mechanism, o.rule_id, o.window_start, o.window_end,"
        " o.n_post, o.label"
        " FROM episodes e LEFT JOIN outcomes o"
        " ON o.episode_id = e.episode_id"
        " ORDER BY e.scene, e.cutoff")
    return [{"episode_id": r[0], "scene": r[1], "cutoff": r[2], "n_pre": r[3],
             "cells_pre": r[4], "top_mechanism": r[5], "rule_id": r[6],
             "window_start": r[7], "window_end": r[8], "n_post": r[9],
             "label": r[10]} for r in rows]


def add_trace(con: sqlite3.Connection, label: str, role: str,
              iteration: int, request_hash: str, response_hash: str,
              violations: list, stopped_because: str,
              response_chars: int = 0) -> int:
    """Log one model call. Insert-only; the stop reason is required."""
    cur = con.execute(
        "INSERT INTO traces(label, role, iteration, request_hash,"
        " response_hash, violations, stopped_because, response_chars,"
        " recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (label, role, iteration, request_hash, response_hash,
         json.dumps(sorted(str(v) for v in violations)), stopped_because,
         response_chars, _now()))
    return cur.lastrowid


def traces_for(con: sqlite3.Connection) -> list:
    cols = ("rowid", "label", "role", "iteration", "request_hash",
            "response_hash", "violations", "stopped_because",
            "response_chars", "recorded_at")
    return [dict(zip(cols, r)) for r in
            con.execute("SELECT rowid, label, role, iteration, request_hash,"
                        " response_hash, violations, stopped_because,"
                        " response_chars, recorded_at FROM traces"
                        " ORDER BY rowid")]


def add_proposal(con: sqlite3.Connection, track: str, status: str,
                 issue: str, recurrence: int, change: dict,
                 cited_episodes: list, cited_traces: list,
                 rejected: list, base_rules_sha: str = "") -> int:
    cur = con.execute(
        "INSERT INTO proposals(track, status, issue, recurrence, base_rules_sha,"
        " change_json, cited_episodes, cited_traces, rejected, recorded_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (track, status, issue, recurrence, base_rules_sha,
         json.dumps(change, sort_keys=True),
         json.dumps(sorted(str(e) for e in cited_episodes)),
         json.dumps(sorted(int(t) for t in cited_traces)),
         json.dumps(list(rejected)), _now()))
    return cur.lastrowid


def proposals_for(con: sqlite3.Connection) -> list:
    cols = ("rowid", "track", "status", "issue", "recurrence",
            "base_rules_sha", "change_json", "cited_episodes",
            "cited_traces", "rejected", "recorded_at")
    rows = con.execute(
        "SELECT rowid, track, status, issue, recurrence, base_rules_sha,"
        " change_json, cited_episodes, cited_traces, rejected, recorded_at"
        " FROM proposals ORDER BY rowid")
    return [dict(zip(cols, r)) for r in rows]


def add_replay(con: sqlite3.Connection, proposal_id: int, result: dict) -> int:
    cur = con.execute("INSERT INTO replays(proposal_id, result_json, recorded_at)"
                      " VALUES (?,?,?)",
                      (proposal_id, json.dumps(result, sort_keys=True), _now()))
    return cur.lastrowid


def replays_for(con: sqlite3.Connection, proposal_id: int) -> list:
    return [{"rowid": r[0], "proposal_id": r[1],
             "result": json.loads(r[2]), "recorded_at": r[3]}
            for r in con.execute(
                "SELECT rowid, proposal_id, result_json, recorded_at"
                " FROM replays WHERE proposal_id=? ORDER BY rowid",
                (proposal_id,))]


def add_verdict(con: sqlite3.Connection, proposal_id: int, decision: str,
                reason: str, operator: str = "") -> int:
    cur = con.execute("INSERT INTO verdicts(proposal_id, decision, reason, operator,"
                      " recorded_at) VALUES (?,?,?,?,?)",
                      (proposal_id, decision, reason, operator, _now()))
    return cur.lastrowid


def verdicts_for(con: sqlite3.Connection, proposal_id: int) -> list:
    cols = ("rowid", "proposal_id", "decision", "reason", "operator",
            "recorded_at")
    return [dict(zip(cols, r)) for r in con.execute(
        "SELECT rowid, proposal_id, decision, reason, operator, recorded_at"
        " FROM verdicts WHERE proposal_id=? ORDER BY rowid", (proposal_id,))]


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
