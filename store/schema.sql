-- BlindSpot study store (P1 persistence). Plain SQL types only, no
-- engine-specific syntax, so the schema ports to Postgres unchanged.
-- Writes are append-only by construction: the access module exposes
-- INSERTs and SELECTs only — there is no update or delete path.
-- Artifact bytes live in repo files; this store pins their SHA-256.

CREATE TABLE IF NOT EXISTS studies (
    id          TEXT PRIMARY KEY,
    domain_id   TEXT NOT NULL,
    frozen_at   TEXT NOT NULL,
    meta        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS artifacts (
    rowid       INTEGER PRIMARY KEY,
    study_id    TEXT NOT NULL REFERENCES studies(id),
    kind        TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    rowid           INTEGER PRIMARY KEY,
    study_id        TEXT NOT NULL REFERENCES studies(id),
    inputs_hash     TEXT NOT NULL,
    rules_hash      TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    cassette_hashes TEXT NOT NULL DEFAULT '[]',
    brief_hash      TEXT NOT NULL,
    operator        TEXT NOT NULL DEFAULT '',
    started_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    seq         INTEGER PRIMARY KEY,
    at          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS study_tokens (
    study_id    TEXT PRIMARY KEY REFERENCES studies(id),
    token_hash  TEXT NOT NULL
);
