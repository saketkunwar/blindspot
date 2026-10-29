# USAGE_DEMO — Replaying the Kalimantan fire study (Demo 2)

End-to-end replay: frozen pre-cutoff prediction → temporal + spatial
holdout checks. Nothing here needs an API key (compute runs with
`--model-round off`; the setup round is the only key-dependent step and
is marked optional). Takes ~5 minutes.

## 1. Prerequisites

- Repo checked out with `demo/fire_study/`, `engine/ledger.py`
  (spec builder), `agents/autoinsight.py`, `agents/context_card.py`.
- Python env with project deps (`shapely`, `pyyaml`).

## 2. Verify the freeze

```bash
sha256sum -c demo/fire_study/BASELINE.sha256
```

Expect all lines OK. Any failure means the inputs moved — stop, do not
recompute over moved inputs.

## 3. Re-run the curation + card (deterministic, no key)

```bash
python demo/fire_study/curate.py
python -m agents.context_card --domain demo/fire_study/domain.json \
  --inputs demo/fire_study/inputs --out-dir demo/fire_study/output
```

Expect `curated 6142 detections, 5 days, 30 cells` and byte-identical
`inputs/` + `output/card.*` (re-check with step 2).

## 4. Re-run the brief (no key) and compare

```bash
python -m agents.autoinsight --inputs demo/fire_study/inputs \
  --rules demo/fire_study/rules.json --domain demo/fire_study/domain.json \
  --out /tmp/fire_replay.json --prompt-log /tmp/fire_prompts \
  --model-round off
diff /tmp/fire_replay.json demo/fire_study/output/brief.json && echo REPLAY-IDENTICAL
```

Expect top mechanism `suppression_then_restart` (~0.84), second
`continued_spread` (~0.11).

## 5. Temporal check (the brief predicts what it never saw)

The ledger only saw detections up to 2026-09-20 (`rules.json: cutoff`).
`inputs/timeline.json` carries the held-out days; the outcome they
confirm — suppression wins in late September, then peat restarts — is
recorded in `QUESTIONS.md` (Demo 2 entry). The check passes when the
step-4 top mechanism matches that outcome without ever reading the
held-out days.

## 6. Spatial check (half the map, same answer)

```bash
# mask the eastern half, recompute with the same frozen rules
python3 - <<'PYEOF'
import json, pathlib, shutil, statistics
src = pathlib.Path('demo/fire_study/inputs')
dets = json.loads((src/'detections.geojson').read_text())['features']
cut = statistics.median(f['geometry']['coordinates'][0] for f in dets)
west = [f for f in dets if f['geometry']['coordinates'][0] <= cut]
out = pathlib.Path('/tmp/fire_holdout/inputs')
shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
(out/'detections.geojson').write_text(json.dumps({"type":"FeatureCollection","features":west}))
for f in ['cells.geojson','timeline.json','extent.json','input_audit.json']:
    shutil.copy(src/f, out/f)
print(f'kept {len(west)}/{len(dets)} detections west of {cut:.4f}')
PYEOF
python -m agents.autoinsight --inputs /tmp/fire_holdout/inputs \
  --rules demo/fire_study/rules.json --domain demo/fire_study/domain.json \
  --out /tmp/fire_holdout.json --prompt-log /tmp/fire_holdout_log \
  --model-round off
```

Expect the same ranking (`suppression_then_restart` top). Identical
probabilities are correct: scoring depends only on which facts are
active, and every gate still passes on half the map.

## 7. Setup round (recorded 2026-10-29; replay offline)

The setup round ran live once (`--no-card`; the card-embedding path
fails its own prompt audit — known issue, see `PROGRESS_ERROR.md`).
It drafted 6 mechanisms, passed the null test, and disagreed with the
frozen rules on top (expected: LLM framing without conviction). Replay:

```bash
python -m agents.setup_study --inputs demo/fire_study/inputs \
  --domain demo/fire_study/domain.json --frozen-rules demo/fire_study/rules.json \
  --brief demo/fire_study/output/brief.json --out-dir /tmp/fsetup --no-card
```

Expect exit 0 from cassette and a draft matching
`output/setup-report-18f6aa3733245198.json`. A fresh live round needs
`BLINDSPOT_LIVE=1` plus `META_MODEL_API_KEY`.

## 8. Full verification

```bash
python3 scripts/validate_hardened.py   # expect ALL PASS (G1-G16)
python3 -m pytest tests/properties/ -q # expect green
bash scripts/judge.sh                  # expect JUDGE OK
```
