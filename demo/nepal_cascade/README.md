# Demo: Nepal cascade autoinsight

A clean, self-contained Nepal-flood demo. The autoinsight pipeline discovers
possible outcomes from **pre-cutoff data only** and ranks an open mechanism
set — including *nothing further happens* — with support-strength
probabilities. The actual event is ground truth used **only afterward** to
check the ranking. Nothing about it leaks into the prediction run.

## Confirmed timeline (Step 0, from the data + web sources)

- **T1 = 2026-09-04T03:56:20Z**, **T2 = 2026-09-09** (both derived from the
  cascade file's own interval boundaries, not typed in anywhere).
- The flood outline is static ("Observed 27 August") — it carries no time
  signal; all change evidence comes from damage geometry.
- The later boundary (T2→T3 group) is fenced, not load-bearing: the demo's
  core claim needs only T1/T2.
- The 12-of-400 segment claim from hindsight analysis is an **overfitting
  trap**: our frozen rule reproduces the *test* (34 pre-cutoff features near
  the target reach = HIT under the frozen threshold), not the hindsight
  number. Match/mismatch is reported as-is.

## Layout

- `curate.py` — build-time step: derives the cutoff from the data, writes
  only pre-T1 bytes to `inputs/` (timestamps and stage labels stripped).
- `inputs/` — curated prediction inputs + `input_audit.json` (source → hash).
- `rules.json` — FROZEN mechanism set, weights, cluster rule, caution prior.
  Changing anything after the insight run needs a new tag + full re-run.
- `probe_model.py` — Step-0 knowledge probe for the model choice.
- `output/brief.json` — the frozen prediction artifact (served by the API).
- `output/prompt-*.txt` — verbatim audited model prompt(s).

## Prediction path (no ground truth readable)

```
python3 -m agents.autoinsight --model-round off     # symbolic, deterministic
python3 -m agents.autoinsight --model-round on      # + model round (needs cassette or live key)
```

`agents/autoinsight.py` refuses anything under `data/raw` by construction.
Prompts are anonymized (no place names, no dates, hypotheses only) and
audit-scanned against tokens drawn from the inputs themselves.

## Model choice (Step 0 finding)

Primary: `muse-spark-1.2-contributor`. Meta publishes no cutoff for either
Contributor SKU, but independent probes measure Spark 1.2's effective
knowledge at late 2025 / January 2026 — before the August 2026 flood — and
it shipped 5 August 2026, so it structurally cannot recall the event.
Fallback: `muse-spark-1.3-contributor` (shipped September 2026, may know the
event) strictly behind anonymized prompts. The live confirmation probe
(`probe_model.py`) runs when a key is available; until then the shipped
prediction is the symbolic path, which uses no model memory at all — the
strongest possible hindsight-freedom. Anonymized prompts are used regardless.

## Presentation

Run instructions live in [USAGE_DEMO.md](USAGE_DEMO.md) (API + web replay).
The page renders only pipeline outputs: hero verdict, evidence cards,
how-it-works, mechanism ranking, findings, legend map. Reference layout was
a guide; no reference figures are copied.
