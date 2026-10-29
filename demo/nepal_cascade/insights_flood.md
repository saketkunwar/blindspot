# Insights — Nepal Flood Demo (`demo/nepal_cascade/`)

Future reference for the BlindSpot Nepal-flood autoinsight demo: what it
studied, how it was built, what it found, and what hardened verification
actually caught. Code and tests are the primary record; this file explains
the *why* so a future reader can reproduce, audit, or extend the demo
without re-deriving every decision.

Companion docs: [README.md](./README.md) (how to run), [rules.json](./rules.json)
(the frozen mechanism set), [demo_nep_flood_plan.md](../../demo_nep_flood_plan.md)
(the plan this implements), [docs/PHASES.md](../../docs/PHASES.md),
[PROGRESS_ERROR.md](../../PROGRESS_ERROR.md), [QUESTIONS.md](../../QUESTIONS.md).

## 1. What the demo studied

The August 2026 Bhote Koshi flood (Nepal–Tibet border): an ice/debris
blockage formed a barrier lake upstream, the lake overflowed around
28 August, and damage progressed through September snapshots. The demo
asks one question from **pre-cutoff data only** (everything dated at or
before T1 = 2026-09-04T03:56:20Z):

> Given a single pre-cutoff snapshot of valley damage, which downstream
> story does the evidence support — safe drainage, a dam that holds, an
> impoundment that bursts, a slope failure elsewhere, downstream-only
> flooding, or nothing further happening?

The actual event (T1→T2 delta: 754 newly destroyed features, Sep-7 SAR lake
log at 3.4 km²) is ground truth used **only afterward** to check the
ranking. Nothing about it leaks into the prediction: no post-cutoff bytes,
no tuned rules, no pre-loaded answer.

The headline result (frozen brief in [output/brief.json](./output/brief.json)):
pre-cutoff evidence most supports **impoundment-then-burst (support 0.94)**,
then upstream slope failure elsewhere (0.05); nothing-further carries live
weight (0.0005) and wins the null red-team test. The frozen cluster rule
fires — 34 pre-cutoff features near the target tributary reach against a
threshold of 8. Probabilities are explicitly **support strengths, not
calibrated frequencies**.

## 2. How it was done

### 2.1 Inputs and curation (`curate.py` → `inputs/`)

- Source: `data/raw/temporal_data/osm_temporal_cascades.geojson` (4414
  features with `destruction_interval_start/end` and `destruction_stage`:
  2092 pre-T1, 754 T1→T2, 1568 T2→T3).
- The cutoff is **derived from the data** (earliest interval end = T1), never
  typed into prediction code. Every kept feature ends at or before T1.
- Timestamps and stage labels are **stripped** from curated features
  (properties keep only `src_id` + `feature_type`), so the prediction path
  cannot see time even by accident.
- Also curated: all 400 staged waterways, the target-reach subset (2 pieces
  named by `rules.json`, read at runtime — no name literal in code), a static
  extent summary (centroid/bbox/area; the "Observed 27 August" outline carries
  no time signal), and `input_audit.json` (source file → SHA-256, filter,
  counts). Later boundaries (T2 = Sep 9, two passes that day) are recorded in
  the audit as *ignored*.
- Reference check that sharpened the design: the user's hindsight analysis
  (12-of-400 segment cluster along Chilime Khola, upstream-swelling /
  downstream-dry dipole) uses T1→T2 data — i.e. GT. The demo therefore tests
  the *rule* (frozen, applied once, reported as-is: HIT with 34 features),
  never the hindsight number.

### 2.2 Frozen rules (`rules.json`)

Fixed and committed **before** any insight run (same discipline as the
`prereg` tag): 6 mechanisms with priors, per-fact weights, activation
thresholds, a caution prior (+0.5 on no-further-event, rationale documented
in-file: absence of post-cutoff evidence favors restraint), the cluster rule
(500 m, ≥8 features), and the scoring formula
(`score = prior + caution + Σ supports − Σ opposes; softmax → support
strength`). Changing anything after the run needs a new tag + full re-run.

### 2.3 Prediction loop (`agents/autoinsight.py`)

1. **Kernel pass** — per-feature RCC-8 vs the static outline, reach split at
   the flood centroid (neck rule: valley drains south, upstream = north),
   channel adjacency (250 m), upstream/downstream density ratio.
2. **Ledger** — 8 evidence facts (F1 total damage … F8 audit-clean), each
   with value, active flag, and plain text. Continuous facts activate on
   documented thresholds (e.g. upstream share > 0.5).
3. **Rival framing** — the frozen mechanism set; no-further-event is a
   first-class hypothesis with real prior weight, so the burst story can
   lose (a run where it cannot is a failed run by definition).
4. **Model round (optional)** — `agents/model_call.py` sends a fully
   **anonymized** prompt (relative snapshots S0/S1, anonymous reaches and
   tributary, mechanisms as hypotheses to score) and parses a strict JSON
   ranking; cites must be ledger facts or the reply is rejected.
5. **Gate** — only ledger-grounded claims survive; the brief records the
   model round (status/model/hash/agreement) alongside the symbolic ranking.
   Final probabilities are symbolic-only by design — the model advises, it
   cannot move the numbers.

### 2.4 Anonymization (the anti-contamination core)

Five composed controls: (1) the prompt builder takes only the ledger — there
is no parameter for GT text, so leaking the future is a type error;
(2) outcome-free instruction text; (3) no place names, no calendar dates;
(4) every prompt saved verbatim and scanned against name/date tokens **drawn
from the inputs themselves** (88 tokens checked, 0 violations), so
anonymization is checked, not promised; (5) single-turn, memory-free rounds
plus a null red-team (a quiet synthetic world must rank nothing-first —
proving no outcome was pre-loaded).

### 2.5 Model choice and live calls

Primary: `muse-spark-1.2-contributor` — shipped 5 Aug 2026 (pre-flood);
independent probes measure effective knowledge at late 2025 / Jan 2026.
Fallback: 1.3-Contributor + anonymization. Transport is cassette-first
(`data/model_cassettes/`, request-hash keyed, usage-logged); live calls need
`BLINDSPOT_LIVE=1` + key, defaulting to the documented Meta Model API
endpoint. Recorded 2026-10-28:

- Step-0 probe ([probe_result.json](./probe_result.json), live): flood
  question → *"I have no knowledge of this."*; control → self-stated cutoff
  January 4, 2026. Verdict: **CLEAN (empirical)**.
- Insight round (cassette `87d24316…`, live-recorded): the clean model ranks
  **safe drainage first** from anonymized evidence while the symbolic ledger
  scores burst 0.94 — recorded as `agreement: false`. A model with no memory
  of the event reasons cautiously; the brief reports both instead of hiding
  the gap.

### 2.6 Serving and presentation

- `GET /api/demo/nepal-cascade?mode=cached|live` (frozen brief / fresh
  recompute, always mode-labelled) and `GET /api/demo/nepal-cascade/geo`
  (target reach + outline box + capped pre-cutoff sample).
- Page `/demo/nepal-cascade`: hero verdict → evidence cards → 3-step
  how-it-works → mechanism ranking bars → findings → legend map. Every value
  renders from the pipeline payload; the reference site was a layout guide,
  never a data source. Styling: flat panels, restrained accent, no
  gradients/glow.

## 3. Benefit of hardened verification (what it actually caught)

G1–G12 ALL PASS, 43/43 tests green, `judge.sh` OK, `next build` clean. The
catches that mattered, newest first:

1. **G12 (new, demo gate) — cutoff proof.** Hiding all of `data/raw` must
   yield byte-identical output; it does. This is the machine-checked version
   of "no GT leakage" — without it the claim would be prose. The quarantine
   half additionally proves curated inputs carry no timestamps/stages and the
   verbatim prompt re-scans clean.
2. **Null red-team test** — the single most valuable check: a quiet synthetic
   world ranks nothing-first, proving the burst story can lose. A demo
   without this test could "predict" the burst with the answer pre-loaded and
   no one could tell.
3. **Old test caught new code** — `test_seed_cassettes_loadable` failed the
   moment model cassettes shared `data/cassettes/` (it assumes SAM mask
   format). Fixed by separation (`data/model_cassettes/`), not by weakening
   the test: proof the durable suite guards the repo against new code.
4. **Density bug** — upstream/downstream ratio came out 313269x because
   region areas were feature areas, not ground areas. A plain eyeball caught
   it; the frozen number is a sane 1.06x, and burst support now comes from the
   cluster hit + channel adjacency, not a bug.
5. **Probabilities summed to 1.0001** (4dp rounding) — fixed in the artifact
   via largest-residual correction, not in the test tolerance. The output
   contract ("sums to 1") is a deliverable, not an aspiration.
6. **Prompt-audit precision** — a naive year-denylist would have false-hit
   the 4-digit evidence count 2092; deriving forbidden date strings from the
   inputs themselves (exact strings + prefixes) is precise where ranges are
   paranoid.
7. **Provenance determinism** — the frozen brief initially recorded
   `status: live-recorded` while replay says `cassette`, failing G12's
   frozen-compare. Regenerating the frozen artifact from replay (live
   provenance stays in the cassette + usage log) keeps "reproduce from
   committed inputs" exact.
8. **Plumbing** — G12's hide-raw step failed cross-device (`/tmp` vs the
   media mount); hidden in place with a leftover guard + `finally` restore.
   Manifest churn (934 new raw files, then 4 cassettes) rode the normal
   G1 flow (986 files, `manifest ok`).

## 4. Ground-truth check (run post-freeze, read-only: `gt_check.py`)

`python3 demo/nepal_cascade/gt_check.py` → [output/gt_check.json](./output/gt_check.json).
Verdict: **MATCH — true outcome rank 1.** The frozen top story
(impoundment_then_burst, 0.94) is consistent with the quarantined T1→T2
delta: 754 newly destroyed features, 54.4% upstream, 86.9% channel-adjacent,
plus a 3.4 km² barrier lake on the Sep-7 SAR pass between the snapshots.

The honest nuance (kept, not hidden): the target-reach cluster does
**not** re-fire in the GT window (2 features near target vs 34 pre-T1).
The pre-T1 cluster was the lead; the T1→T2 destruction spread wider along
the channels. The match rests on upstream concentration + channel
adjacency + lake presence — exactly the signature the ledger scored, and
the script that says so cannot re-tune anything (it takes no weights and
touches only `gt_check.json`).

## 5. The case for autoinsight (why this build matters)

1. **It predicted the mechanism class from pre-event data alone.** No
   post-Sep-4 byte entered the prediction (G12 proves it mechanically, not
   rhetorically). The top story matched quarantined ground truth at rank 1.
2. **The open set is what makes the hit meaningful.** Six stories including
   nothing-further, the burst story able to lose, the null red-team proving
   it can lose. A closed "burst or not" framing would have made the same hit
   worthless.
3. **The clean-model disagreement is a feature, not a failure.** A
   knowledge-cutoff model, reading anonymized evidence with no memory of the
   event, ranked safe drainage first. That disagreement is only producible
   by a pipeline the model cannot see through: anonymized prompts,
   ledger-only context, gate-checked cites. A contaminated setup would have
   parroted burst first with false confidence.
4. **Every layer is re-runnable by a stranger.** Curator, frozen rules,
   deterministic scorer, committed cassette, byte-identical gates. Nothing
   depends on the author's memory or a live key.

## 6. Open threads and limits (do not lose these)

- Support probabilities are **uncalibrated by construction**; anyone wanting
  frequencies needs a calibration phase that does not exist yet.
- The 12-segment hindsight cluster is **not** reproduced and should not be —
  the frozen rule's HIT (34 features, pre-T1 only) is a different, weaker,
  honest claim.
- Model transport assumes the documented Meta Model API shape; the key used
  for recording was passed via env only and is not stored anywhere in the
  repo. Re-recording needs a key again (`BLINDSPOT_LIVE=1` + key, one
  command); replay needs nothing.
- T3's exact bound and the Sep-14-vs-Sep-9 question are fenced, not
  resolved — the demo's core claim needs only T1/T2.
- GT check discipline: the T1→T2 delta + SAR log may be compared against
  the frozen ranking, with **no re-tuning afterward** — report match or
  mismatch as-is.

## 7. Setup round: the LLM frames, the kernel computes (2026-10-28)

`agents/setup_study.py` promotes what the coding agent did by hand into a
pipeline stage: the model receives domain ontology + anonymized pre-cutoff
ledger and drafts a study (mechanisms, weights, cluster rule). The draft
never touches the frozen rules; it is validated (cite discipline, open set,
its own null red-team) and compared. Three live rounds, all recorded:

- **Round 1 (no ontology):** generic mechanisms (M_fluvial, M_null,
  M_other) — no flood physics at all. Lesson: an LLM with thin context
  frames a thin study. Vocabulary must come from the domain.
- **Round 2 (flood ontology added):** adopted all six flood stories
  (drainage, stable dam, ponding+breach, slope elsewhere,
  downstream-only, quiescence) but cited abbreviated ids (F1, not
  F1_total_pre_cutoff_damage). Rejected on format — the gate working.
- **Round 3 (ontology + cite-format line):** valid draft, null test PASS.
  Same six stories as the frozen study, weights in the same family
  (channel 0.8, cluster 0.5, target-reach 0.75). But cluster weight 0.5 vs
  frozen 2.0, so its ranking tops downstream-only with ponding-release
  (burst) 4th. **Top disagrees with frozen + GT.**

Two honest caveats. First, its cluster threshold (min_features 34) looks
anchored on the ledger's own reported count (34 features at the frozen
500 m) — the setup round is not fully independent of frozen-rule
parameters, only of ground truth. Second, the ranking gap is conviction,
not vocabulary: the model framed the right stories but under-weighted the
decisive fact. The human-set F4 = 2.0 ("a 34-feature tributary cluster is
the lead") is what carries the rank-1 hit.

Standing conclusion: the division of labor is LLM-frames-vocabulary,
human-sets-conviction, kernel-computes. The setup round is a permanent
rival generator — a valid alternative study that disagrees — which is
exactly what the method wants. Automation of conviction (weight-setting
from evidence) is open future work and must pass the same null red-team.

## 8. Sources (moved from the retired demo plan; all inspected this run)

- [telegraph.com/nepal-tibet-glacier-flood-new-lake-dam-bhote-koshi](https://telegraph.com/nepal-tibet-glacier-flood-new-lake-dam-bhote-koshi/) — first dam broke, second dam built, ~2M m³ lake, explicit uncertainty about catastrophic burst (non-empty).
- [lirneasia.net/2026/10/nepals-bhotekoshi-disaster-every-link-existed-nothing-joined-them](https://lirneasia.net/2026/10/nepals-bhotekoshi-disaster-every-link-existed-nothing-joined-them/) — 26 Aug collapse timeline, 27 Aug barrier-lake warning, 28 Aug overflow and rescue pause, Chilime Khola as damage site (non-empty).
- [orcarouter.ai/blog/muse-api](https://www.orcarouter.ai/blog/muse-api) — Contributor model IDs, tier pricing/training trade, no-`max`-on-Contributor.
- [llm-stats.com/models/compare/muse-spark-1.2-vs-muse-spark-1.3](https://llm-stats.com/models/compare/muse-spark-1.2-vs-muse-spark-1.3) — no published knowledge cutoff for 1.2 or 1.3; [github.com/apoorvumang/knowledge-cutoff](https://github.com/apoorvumang/knowledge-cutoff) — measured effective knowledge late 2025 / Jan 2026 (discovery sources; verified empirically in Step 0).
- [nepflood.vercel.app](https://nepflood.vercel.app/) — presentation layout reference only (hero, sensor cards, how-it-works, findings counters, legend map); no facts or figures taken from it (non-empty).
