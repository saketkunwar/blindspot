# BlindSpot tiered memory — M0: rolling-origin fire episodes

M0 proves the mechanics of tiered memory on the Kalimantan fire scene before
any memory claim is made: slide cutoffs through stored FIRMS detections,
recompute the frozen study ranking from pre-cutoff data only, and label each
episode's outcome with a preregistered rule. No tiered-memory promotion is
granted here; the census below is the evidence a later milestone must beat.

## Rule (preregistered)

Source: [config/preregistered_memory.yaml](/run/media/saket/7d6272d9-0cb8-48f8-a77f-733284bb7f36/home/saketkunwar/blindspot/config/preregistered_memory.yaml)
(`restart-noisefloor-v1`, decided before the first backtest run).

- **Outcome window:** days strictly after the cutoff through
  `cutoff + look_ahead_days` (2 days).
- **Positive (`restart`):** at least `restart_min_detections` (3, the study's
  FIRMS noise floor) detections inside the window. Fewer detections still
  mean fire, so the negative label is **`quiet`**, never "out".
- **Minimum history:** an episode needs `minimum_history_days` (2) distinct
  burn days on/before its cutoff; thinner cutoffs are skipped, never stored.
- **Unlabelable:** an episode whose window runs past the last observed scene
  day is stored as `unlabelable` and kept in the census so the denominator
  stays honest.

## Lineage

- Scene: `data/fire_kalimantan/firms_kalimantan_c.json`
  (sha256 `62880f99f2425c18b311b4c7ab402b72b730bafd6bc31ab803c5f0e5761636`,
  tag `kalimantan_c`, 6142 detections over 2026-09-16..20).
- Ranking: the frozen study path, unchanged — `engine/ledger.py`
  `compute_ledger_from_spec` + `score_mechanisms` over
  `demo/fire_study/rules.json` with the closed `engine/facts` op set.
  `scripts/backtest_episodes.py` invents no scoring.
- Curation mirror: `day <= cutoff` only (the same comparison as
  `demo/fire_study/curate.py`), sorted `(day, lon, lat)` traversal, floor
  grid of 0.5 deg, hot cells at >= 3 detections, extent from the slice bbox.
  Grid cells and the study box are recomputed per episode from the slice, so
  post-cutoff counts, hot tags, and bounding boxes cannot leak in.
- Check: the episode at the full cutoff reproduces the frozen
  `demo/fire_study/output/brief.json` ledger bit-for-bit (FF1 6142, FF3 30
  cells, FF4 6126, top `suppression_then_restart` at 0.8425) — covered by
  `test_full_cutoff_matches_frozen_brief`.
- Runner: `python scripts/backtest_episodes.py --db <out.sqlite3>
  [--census-out <census.json>]`; scenes are MANIFEST-verified fail-closed.
- Store guard: `outcomes` enforces one row per `(episode_id, rule_id)`, so a
  duplicate outcome fails instead of multiplying census rows.

## Census (observed 2026-10-30, `restart-noisefloor-v1`)

| episode | cutoff | n_pre | cells | top | window | n_post | label |
|---|---|---|---|---|---|---|---|
| kalimantan_c@2026-09-17 | 2026-09-17 | 503 | 14 | suppression_then_restart | 2026-09-18..2026-09-19 | 4793 | restart |
| kalimantan_c@2026-09-18 | 2026-09-18 | 1603 | 20 | suppression_then_restart | 2026-09-19..2026-09-20 | 4539 | restart |
| kalimantan_c@2026-09-19 | 2026-09-19 | 5296 | 29 | suppression_then_restart | 2026-09-20..2026-09-21 | 846 | unlabelable |
| kalimantan_c@2026-09-20 | 2026-09-20 | 6142 | 30 | suppression_then_restart | 2026-09-21..2026-09-22 | 0 | unlabelable |

Plus one skipped cutoff (2026-09-16: 1 history day < 2). Totals: 4 stored
episodes, 2 labelable, 2 unlabelable. Both labelable episodes restart; the
frozen top mechanism agrees with the outcome direction in 2/2 cases — a
consistency note, not a skill claim (n = 2 cannot support one).

## Verdict: STOP for promotion, GO for M0 mechanics

- **STOP** promoting anything to tiered-memory M1: the promotion bar
  (10+ labelable episodes across 3+ scenes) is not met — 2 labelable
  episodes in 1 scene. More stored scenes with post-cutoff span are needed,
  not a re-reading of these episodes.
- **GO** on M0 mechanics: the backtest runs leak-free (truncation probes in
  `tests/properties/test_memory_episodes.py`), deterministically (reruns are
  census-identical), and reproduces the frozen brief at full cutoff.
- **Gate follow-ups (same day):** the M0 full gate surfaced two failures and
  both were fixed at root cause — G3 now skips `web/app/demo/**`
  presentation prose (a pre-existing trip on the committed fire demo page,
  not an M0 file), and `results/store.sqlite3` was reseeded for the new
  episode/outcome tables so the G17 drill passes content-identical. Full
  gate green; see `PROGRESS_ERROR.md` for the entry.

---

# M1: the memory read path (2026-10-30)

M0 proved episodes can be built leak-free. M1 lets a brief *read* them —
as a second, clearly labelled ranking beside the frozen one, never a
replacement. The frozen `mechanisms` ranking is untouched in every case;
memory only ever adds a `memory` section, and only when it has enough past
to deserve a voice.

## Read-path parameters (preregistered, config v2)

Source: `config/preregistered_memory.yaml` (`version: 2`, same `rule_id` —
v2 adds read-path values only; episode/outcome rows are unaffected).

| Value | Reason it is what it is |
|---|---|
| Signature: active fact ids + coarse count bins `[1, 3, 10, 100, 1000, 10000]` | Counts are bucketed so small-count noise cannot split one pattern in two; with so few episodes, fine bins would leave every pattern with a history of one. Non-integer values are already categorical and used verbatim. |
| `min_episodes_to_speak: 5` | The smallest count at which a smoothed rate starts to mean anything. Below it the brief carries no memory section at all. |
| `smoothing_alpha: 1.0` | One imaginary observation per side: with tiny histories the rate stays near neutral instead of swinging on a single case. |
| `max_abs_shift: 0.10` | Memory may nudge a frozen probability by at most ten points — a second opinion, never a veto. Shifts are renormalized so the adjusted ranking stays a valid distribution. |
| `outcome_supports` mapping | Written for the fire domain, the only one with episodes: a restart is what suppression-then-restart predicts; a quiet window is what stay-out and burn-out stories predict. Mechanisms no label supports keep shift 0. |

## The one rule that prevents hindsight

Every read takes an `--as-of` day and keeps only labelled episodes whose
outcome window had already closed by then. A window always ends after its
own episode's cutoff, so anything still open at `as_of` is knowledge the
case could not have had yet. Missing `--as-of`, a malformed one, or a
missing store file fails the run instead of guessing. The store is opened
read-only; memory never creates, migrates, or writes it.

## Operator use

- `python -m agents.autoinsight --memory-db <episodes.sqlite3> --memory-config config/preregistered_memory.yaml --as-of <ISO-day> ...` writes the brief with a `memory` section when history suffices, byte-identical without it when it does not.
- `python scripts/status.py --memory-db <episodes.sqlite3>` prints a MEMORY table: one row per pattern (episodes seen, labelled, outcome labels). Build a store with `python scripts/backtest_episodes.py --db <out.sqlite3>`.
- The section's sentence restates the ledger's `memory` block exactly; `engine/memory.py:validate_memory_section` checks that, and the brief refuses to write on mismatch.

## Current state: honestly silent

The census holds 2 labelable episodes against a threshold of 5, so every
brief built today carries no memory section — verified byte-for-byte, not
promised. G19 pins that silence (empty-memory briefs equal the frozen
baselines on both studies); G20 pins the hindsight rule (deleting every
row a case could not have known leaves the brief byte-identical, with the
delete count asserted so the gate cannot pass vacuously). The adjust math
itself is pinned by unit tests on synthetic histories, ready for the day
real history crosses the threshold.

---

# M2: honest measurement (2026-10-30)

M2 asks whether the adjust math can manufacture skill from noise, before
anyone trusts it with real history. `scripts/measure_memory.py` runs two
preregistered arms (config v3 `null_test`: seed 7, 200 trials, histories of
8, a four-story ranking with a clear but fallible favorite):

- **Null arm** (labels are coin flips): adjusted must not beat frozen by
  more than 0.02. Observed: **−0.130**. It loses — capped shifts still
  chase noise, which is the finding, not a failure.
- **Signal arm** (labels always back the true winner): adjusted must gain
  at least 0.05. Observed: **+0.270**. The positive control proves the
  test can see real help when it exists.

G21 runs this script and fails the phase if either arm misbehaves. The
stronger sentence goes in the operator's handbook: once memory speaks, an
uninformative history actively hurts — the speaking threshold keeps memory
silent at 2 episodes, but it cannot protect a long noisy history. Fixing
that (an evidence-strength gate before speaking) is recorded as a
candidate Track B proposal, not a quiet retune of the math.

## M3a: proposal discipline and traces (2026-10-30)

The evolver may propose, test, and wait for a human — never apply. The
machinery, all deterministic and offline-testable:

- **Traces** (`store/schema.sql`, `agents/setup_study.py --traces-db`):
  one row per model call with request/response hashes, violations, and a
  closed-vocabulary stop reason. Rounds are single-turn by construction,
  proven by counting the model calls during a cassette replay, not by
  reading the code. The cassette layer reports no token counts, so the
  table records response length instead of inventing a number.
- **Structural checks** (`engine/evolution.py:validate_proposal`): exactly
  one change, a supported kind (Track B opens weight-only), a written
  issue, recurrence at or above the bar over independent cutoffs
  (`independent_cutoffs`: slides less than `independence_gap_days` apart
  count once), cited ids that exist, and a base file that matches a frozen
  study. Candidates (issue + evidence, no complete change) are never
  reviewable — approving one is refused.
- **One hill-climbing step** (`scripts/hill_climb.py`): mines traces for
  violations recurring across independent runs and patterns whose frozen
  top no observed outcome backs, files at most `max_proposals_per_run`
  candidates, then stops. No model, no application, no reads past
  `--as-of`. On today's data the correct output is "nothing meets the
  bar" (exit 0): two labelled episodes qualify no pattern, and clean
  setup replays leave no recurring violation.
- **The evolver's own instructions** (`agents/evolver/AGENTS.md`, two
  skills): versioned, human-reviewed, changeable only by a new version.
  They bind future model proposers; nothing in them can move a number.
- G23 pins the caps (sane block, per-run cap enforced on a constructed
  two-issue input, single-trace-row rounds). G24 pins feedback honesty
  (the analyzer report rebuilt without future rows is byte-identical,
  prune count asserted).

## M3b: held-out replay and human review (2026-10-30)

- **Skeptic** (`engine/evolution.py:skeptic_replay`): replays a weight
  change on held-out episodes — roles rebuilt from the pinned scene files,
  never from stored summaries — and scores frozen versus proposed by how
  often each top story is backed by the outcome. Time splits old-to-new
  (`time_slices`): propose on the early span, validate on the middle, and
  the final slice selection never touches. Cited evidence reaching the
  validation span contaminates the replay and refuses approval.
- **Review** (`scripts/review_proposals.py`): submit (validates, files
  pending), replay (appends results, never overwrites), approve/reject
  (both need written reasons; approve needs a replay that beats frozen by
  `min_win_margin` on at least one held-out episode with the frozen top
  kept, or an explicit `--override` recorded just as loudly; decided
  proposals stay decided). Approval writes the verdict first, then the
  modified rules to a live file under `results/` — never into the frozen
  demo directory. Tagging and freezing stay human hands.
- G22 pins the discipline: every unsafe path refused, verdicts unable to
  dangle, frozen briefs untouched throughout.
- **Today's honest state:** the validation span holds no labelled
  episodes, so no proposal can earn approval — the CLI proves it by
  refusing. The approve path with a clearing replay is unit-proven on
  synthetic histories and override-proven end-to-end; its first real use
  waits for real history.
