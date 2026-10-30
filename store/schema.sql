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

-- BlindSpot tiered-memory milestone M0: rolling-origin fire episodes.
-- Append-only like everything else: INSERTs and SELECTs only. One row per
-- (scene, cutoff); the prediction slice is exactly detections with
-- day <= cutoff, recomputed per episode so no post-cutoff byte leaks in.
CREATE TABLE IF NOT EXISTS episodes (
    episode_id    TEXT PRIMARY KEY,
    scene         TEXT NOT NULL,
    scene_sha256  TEXT NOT NULL,
    cutoff        TEXT NOT NULL,
    n_pre         INTEGER NOT NULL,
    days_pre      TEXT NOT NULL DEFAULT '[]',
    cells_pre     INTEGER NOT NULL,
    facts_json    TEXT NOT NULL DEFAULT '{}',
    ranking_json  TEXT NOT NULL DEFAULT '[]',
    top_mechanism TEXT NOT NULL,
    recorded_at   TEXT NOT NULL
);

-- Outcomes are labelled later by the preregistered memory rule, never by
-- hand: one row per (episode, rule). Episodes whose look-ahead window runs
-- past the observed scene span stay 'unlabelable' — an honest census keeps
-- them instead of dropping them. UNIQUE(episode_id, rule_id) keeps the
-- census join honest: a duplicate outcome fails instead of fanning out rows.
CREATE TABLE IF NOT EXISTS outcomes (
    rowid         INTEGER PRIMARY KEY,
    episode_id    TEXT NOT NULL REFERENCES episodes(episode_id),
    rule_id       TEXT NOT NULL,
    lookahead_days INTEGER NOT NULL,
    window_start  TEXT NOT NULL,
    window_end    TEXT NOT NULL,
    n_post        INTEGER NOT NULL,
    label         TEXT NOT NULL,
    recorded_at   TEXT NOT NULL,
    UNIQUE (episode_id, rule_id)
);

-- Tiered-memory M3: the evolution record. Insert-only like everything
-- else. Traces log every model call (one row per call, stop reason
-- recorded); proposals hold rule/instruction changes (candidates name an
-- issue with evidence but no complete change and can never be approved;
-- pending proposals carry exactly one change and are validated before
-- insert); replays append Skeptic held-out results (re-running appends, it
-- never overwrites); verdicts record the human decision with its reason.
CREATE TABLE IF NOT EXISTS traces (
    rowid         INTEGER PRIMARY KEY,
    label         TEXT NOT NULL,
    role          TEXT NOT NULL,
    iteration     INTEGER NOT NULL,
    request_hash  TEXT NOT NULL,
    response_hash TEXT NOT NULL,
    violations    TEXT NOT NULL DEFAULT '[]',
    stopped_because TEXT NOT NULL,
    response_chars INTEGER NOT NULL DEFAULT 0,
    recorded_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    rowid         INTEGER PRIMARY KEY,
    track         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'candidate',
    issue         TEXT NOT NULL,
    recurrence    INTEGER NOT NULL,
    base_rules_sha TEXT NOT NULL DEFAULT '',
    change_json   TEXT NOT NULL DEFAULT '{}',
    cited_episodes TEXT NOT NULL DEFAULT '[]',
    cited_traces  TEXT NOT NULL DEFAULT '[]',
    rejected      TEXT NOT NULL DEFAULT '[]',
    recorded_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replays (
    rowid         INTEGER PRIMARY KEY,
    proposal_id   INTEGER NOT NULL REFERENCES proposals(rowid),
    result_json   TEXT NOT NULL,
    recorded_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verdicts (
    rowid         INTEGER PRIMARY KEY,
    proposal_id   INTEGER NOT NULL REFERENCES proposals(rowid),
    decision      TEXT NOT NULL,
    reason        TEXT NOT NULL,
    operator      TEXT NOT NULL DEFAULT '',
    recorded_at   TEXT NOT NULL
);
