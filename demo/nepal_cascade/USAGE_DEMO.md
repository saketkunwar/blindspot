# USAGE_DEMO — Replaying the Nepal demo on the web app

## DEMO 1: Nepal cascade autoinsight (`/demo/nepal-cascade`)

End-to-end replay: frozen pre-cutoff prediction → API → presentation page.
Takes ~5 minutes. Nothing here needs an API key (replay uses the committed
cassette); the live-call variant is marked optional.

### 1. Prerequisites

- Repo checked out with the demo files present: `demo/nepal_cascade/`,
  `agents/autoinsight.py`, `agents/model_call.py`, `tests/properties/test_demo_nepal.py`.
- Python env with project deps (`fastapi`, `shapely`, `pydantic`, `pyyaml`,
  `httpx`/`requests` for tests) and Node 18+ with `web/node_modules`
  installed (`cd web && npm install` on first use).
- Ports 8000 (API) and 3000 (web) free.

### 2. Start the API (terminal 1)

```bash
uvicorn api.server:app --port 8000
```

Sanity check (terminal 2):

```bash
curl -s localhost:8000/api/demo/nepal-cascade | head -c 300; echo
curl -s localhost:8000/api/demo/nepal-cascade/geo | head -c 200; echo
```

Expect HTTP 200 with `{"mode":"cached","data":{...}}` (frozen brief) and a
`layers` payload (target reach + outline + 500-feature pre-cutoff sample).

### 3. Start the web app (terminal 2)

```bash
cd web && npm run dev
```

Open **http://localhost:3000/demo/nepal-cascade** in a browser.

### 4. What you should see (in order)

1. **Hero** — title, verdict line
   ("Pre-cutoff evidence most supports 'Impoundment grows, then the dam
   bursts'"), the support-strength disclaimer, snapshot label, mode badge.
2. **Evidence cards** — 8 ledger facts (F1 total damage … F8 audit-clean).
3. **How it works** — Detect → Classify → Cascade (static explainer).
4. **Mechanism ranking** — 6 bars from the payload; burst first (~94%),
   nothing-further last but non-zero.
5. **Findings** — cluster finding (HIT, 34 features), model-round status,
   prompt-audit count (88 tokens, 0 violations), pre-cutoff counts
   (2092 of 4414).
6. **Legend map** — target reach, observed outline, pre-cutoff damage
   sample (503 layers drawn; caption states the cap).

If any number on screen differs from `demo/nepal_cascade/output/brief.json`,
the page is stale — hard-refresh (the page fetches with `cache: no-store`).

### 5. Re-run the prediction behind the page (optional, no key)

```bash
python3 -m agents.autoinsight --model-round on --out /tmp/replay.json --prompt-log /tmp/replay_prompts
diff /tmp/replay.json demo/nepal_cascade/output/brief.json && echo REPLAY-IDENTICAL
```

Then reload the API in live mode and refresh the page:

```bash
curl -s "localhost:8000/api/demo/nepal-cascade?mode=live" | head -c 200; echo
```

Expected: byte-identical brief (cassette replay, fully offline).

### 6. Full verification (optional, ~4 min)

```bash
python3 scripts/validate_hardened.py   # expect G1–G12 ALL PASS
python3 -m pytest tests/properties/ -q # expect 62 passed
bash scripts/judge.sh                  # expect JUDGE OK
python3 demo/nepal_cascade/gt_check.py # expect MATCH, true outcome rank 1
```

### 7. Live model call (optional, needs key)

```bash
export META_MODEL_API_KEY='<key>'; export BLINDSPOT_LIVE=1
python3 -m agents.autoinsight --model-round on   # records/refreshes cassette
python3 demo/nepal_cascade/probe_model.py        # Step-0 contamination probe
```

The key travels via environment only — never paste it into files. A fresh
live call changes `model_round.status` in the brief; re-freeze deliberately
(see [insights_flood.md](./insights_flood.md) §3.7) and re-run §6, or keep
the committed cassette as the frozen artifact.

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Page shows "API unreachable" | API not running or wrong port; check terminal 1, or set `NEXT_PUBLIC_API_URL=http://localhost:8000` when starting web |
| Map empty, rest renders | MapLibre CDN style unreachable (offline env); everything else is API-driven and still valid |
| `mode=live` 502s | Prediction crash — read `stderr` tail in the response; inputs dir must be intact |
| G12 FAIL "differs from frozen brief" | Brief was regenerated (e.g. after a live call) — either re-freeze deliberately or restore `output/brief.json` and re-run |
| `manifest ok` fails with unlisted files | New files under `data/` need `python3 scripts/make_manifest.py` + source fill (see [insights_flood.md](./insights_flood.md) §3.8) |

### 7. Operator runbook — keys, cassettes, status (P3)

**Keys travel via environment only.** `BLINDSPOT_LIVE=1` plus
`META_MODEL_API_KEY` (endpoint override: `META_MODEL_API_URL`); the
operator token for live API mode is `BLINDSPOT_OPERATOR_TOKEN`. No key
is ever written to a file, a cassette, or a log — there is a durable
test pinning this (`test_auth.py`). Rotate by replacing the env value;
recorded cassettes keep working (they are keyed by request hash, not by
credential).

**Record → replay → freeze.** A builder change alters the setup prompt,
so the old cassette misses and the round needs one live call:

```bash
export BLINDSPOT_LIVE=1 META_MODEL_API_KEY='<key>'
python3 -m agents.setup_study --inputs demo/nepal_cascade/inputs \
  --domain demo/nepal_cascade/domain.json --out-dir /tmp/rec --no-card
```

Copy the resulting `setup-prompt-*.txt` + `setup-report-*.json` into
`demo/nepal_cascade/output/` (fire study: `demo/fire_study/output/`),
register any new cassette with the record workflow below, pin the new
files in `BASELINE.sha256`, and re-run §6. Replay stays offline:
unset `BLINDSPOT_LIVE` and re-run — the draft must match a committed
one (G14 checks this in CI).

**Manifest registration.** One new file: `python3
scripts/check_manifest.py --data-dir data --record <path> --kind
real|synthetic|perturbed --source-url <url> --license <licence>`.
Bulk rebuild after a large ingest: `python3 scripts/make_manifest.py`,
then fill every `FILL ME` before the gate runs. Never hand-edit
`MANIFEST.json`.

**One-command status.** `python3 scripts/status.py` prints studies,
runs, model usage, and the setup gates; exit 1 means a seeded artifact
fails its hash check. Nightly CI (`.github/workflows/nightly.yml`)
runs the full gate + judge + web build and files an issue on failure —
never auto-fixes.
