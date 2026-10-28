# PROGRESS_ERROR.md — top findings and what hardened verification caught, per phase

> Standing rule: after every phase, append a section here with the phase's top
> finding, every error the gates/tests caught, and how useful each catch was.
> Newest phase goes at the bottom. Nothing here changes the plan; it records
> what the verification actually earned.
>
> Legend — every catch below is tagged:
> - `[hardened]` = a G1–G10 gate (`scripts/validate_hardened.py` / `judge.sh`):
>   fail-closed, machine-enforced, blocks the phase. Skipped = failed.
> - `[plain]` = durable property tests, generator self-checks, or manual
>   inspection: strong signal, but advisory unless a hardened gate invokes it
>   (G10 pulls the durable suite into the hardened set on full runs).

## Phase 0 — Setup (repo skeleton, data staging, prereg freeze)

Top finding: the workspace had no repo, no `AGENTS.md`, and raw data in
non-spec paths (`data/nepflood_cascade/...`); the spec layout, manifest, and
frozen config all had to be built before any pipeline could be trusted.

- `[hardened]` G9 held the line — `prereg` tag plus frozen-config check
  blocked any pipeline work until `c3c5606` was committed and tagged.
  Usefulness: high; without the tag gate, config values could have drifted
  after seeing results. (G1/G2/G8 were green on first run — also hardened,
  but they confirmed rather than caught.)
- `[plain]` Inspection (recorded, not guessed): `AGENTS.md` missing (spec
  says "read AGENTS.md first") — created a minimal one pointing at the spec
  and plan. FIRMS layout confirmed as dict-with-`detections` for the
  Kalimantan scenario file; flood geometries catalogued per file. Usefulness:
  medium; these become loader requirements in Phase 3 instead of runtime
  surprises.
- `[hardened]` Standing risk logged, not yet tested: the 150 ha evasion
  threshold is unworkable as literally written (one VIIRS pixel ≈ 14 ha);
  D-4 redefines the per-cell cap by rule. The full hardened run (G4–G7)
  cannot execute until pipelines exist — that is the next gate, not a pass.

## Phase 1 — Kernel (`engine/`)

Top finding: the durable tests caught a real table-ordering bug before it
could poison propagation; fixed and verified.

- `[plain]` `test_rcc8_table_verified_properties` + `test_path_consistency`
  caught the table-ordering bug: the 8×8 composition rows were zipped against
  `RCC8_RELATIONS` (EQ sorts 4th) instead of table order, silently shifting
  every row after PO (e.g. TPP;EC came out `{DC}` instead of `{DC, EC}`).
  Fix: explicit `_TABLE_ORDER` with a comment. Usefulness: very high; without
  the converse-symmetry + worked-example checks, all downstream inference
  (propagation, continuity, detectors) would have been wrong while looking
  structurally fine. (Runs under G10 on full gate runs — plain check,
  hardened enforcement.)
- `[plain]` Same suite caught a test-side bug, not a kernel bug: my
  converse-symmetry assertion had `r`/`c` swapped, failing on correct tables.
  Fix: compare `C[inv[r]][inv[c]]` against `conv(C[c][r])`. Usefulness:
  medium; it proved the checks are strong enough to fail on any asymmetry,
  including my own.
- `[plain]` The generator's textbook-edge assertion (fail-loud `SystemExit`)
  caught the single-enum shortfall: missed TPP→NTPP and DC→EC — coarse grid
  resolution made strict containment unrepresentable and left no buffer cell
  for disjoint staging. Fix: two merged enums (corner 3×3 + centre 2×2) with
  connected/no-crossing toggle rules; teleport jumps (DC↔PO, NTPP↔DC, …)
  verified absent. Usefulness: high; the graph is now derived evidence
  (`engine/neighborhood.json` + witness counts), not a hand-written claim.
- `[hardened]` Gates this phase: G1/G2/G8/G9/G10 ALL PASS, G3 literal scan
  clean. G10 is what turns the durable suite from advisory into blocking on
  full runs. The Phase 3-only gates (G4–G7, pipeline contract) remain
  correctly red/blocked until pipelines exist — that blocking itself is the
  hardened behavior working (a plain test run would just show errors; the
  gate says the phase is not done).

## Phase 2 — Gap auditor

Top finding: the module's riskiest requirement (hypotheses built from t0
before t1 is read) is enforced by the function signature, not by discipline —
`predict_a_rivals` has no t1 parameter, so leaking the future is a TypeError,
not a review catch.

- `[plain]` `shapely.mapping` does not exist (`shapely.geometry.mapping`
  does) — import failed at test collection, before any assertion ran. Fix:
  one-line import correction. Usefulness: low but instant; collection errors
  are the cheapest failures available.
- `[plain]` Two test-data bugs, not auditor bugs: non-lon/lat cell ids
  (`"a"`) crashed the tenth-degree parser, and `"10.5"` vs `"10.0"` cells are
  five grid steps apart, not adjacent, so the evasion component never formed.
  Fix: realistic one-decimal adjacent ids. Usefulness: medium — it confirmed
  the parser is strict (good: Phase 3 cell ids are always lon/lat) and that
  4-connectivity is genuinely distance-sensitive.
- `[hardened]` Setup gates still ALL PASS (22/22 runnable durable tests),
  G3 scan clean. Detector thresholds all flow from the passed-in `cfg`, so
  the no-hardcoded-answers gate holds for the new module with nothing to
  waive.

## Phase 3 — Pipelines

Top finding: the anchor cell reproduces the filed total and day counts from
the data itself (1215 total, 233 on the anchor day) — the binning is exactly
right, and the pitch numbers confirm the data rather than the other way
round. The pipeline disagrees with the pitch only where the pitch is
illustrative (footprint RCC-8 series, which are soft by design).

- `[plain]` Layout A detection dates live in `payload.acq_date`, not
  top-level — the first fire run produced 0 cells because the parser looked
  only at top level. Caught immediately by the empty output, fixed with a
  properties-plus-payload merge fallback. Usefulness: high; a silent empty
  result would have passed every structural check while saying nothing.
- `[plain]` The throwaway shift probe initially failed on exact float
  equality (Haversine differs in the last ulp under translation). Matched to
  the 1e-6 bar both sides use — all pass, worst deviation 8.9e-10.
  Usefulness: medium; it proved the tolerance is load-bearing, not cosmetic.
- `[hardened]` First full gate run: G1–G10 ALL PASS, 25/25 durable tests
  green. G4 (null config exits 2), G5 (both CLIs exit 0), G6 (contract +
  inverses + missing-input honesty) all green on real data for the first
  time. The pipeline-contract tests — fail-closed since setup — finally
  execute instead of erroring, which is itself the milestone.
- `[hardened]` Caveat with a paper trail: external shift harnesses keyed on
  top-level date fields will not move Layout A detection dates; the field to
  shift (`payload.acq_date`) is now documented in QUESTIONS.md and
  `docs/PHASES.md` so the harness can be adapted rather than silently
  disagreeing.

## Hardening pass (G11, numeric G3, committed joint-shift)

Top finding: the gates had a vacuous-truth hole — a structurally valid but
content-empty result passed everything. It is now closed by construction.

- `[hardened]` New G11 (content-vs-input): fire cell counts must sum to the
  reported FIRMS detections, dates must match input days, the claim verdict
  is recomputed independently, flood assets must partition act1. The old
  empty-output failure mode now fails G11 loudly instead of passing G6
  quietly. Verified green on real data.
- `[hardened]` G3 now derives its denylist from live config/data (13
  literals: distinctive floats, long config strings, timeline dates/names)
  instead of three hand-written patterns. Integers and 0.5 are deliberately
  excluded as unenforceable — documented in the gate. Green with no hits.
- `[plain]` Committed `test_shift_invariance.py`: the joint firms+timeline
  shift that previously lived only in a throwaway probe is now a durable
  gate-enforced test (G7 points at it). Caught one fixture bug on the way in
  (shifted dir built twice) — test bug, not product.
- Cost of the hardening: full suite now 27 tests / ~70 s. Accepted; the
  slow tests are the perturbation runs, and they are the point.

## Hardening follow-up — scenario selection check (G11)

Top finding: G11 has now caught something first-hand — on a negative
control. A doctored but self-consistent result (wrong FIRMS file, zero
cells, otherwise valid) fails the new selection check with the exact
message the original payload-date incident deserved.

- `[hardened]` G11 recomputes the file-selection rule (timeline site ↔ tag,
  fallback most-in-window, then most overall) and rejects any reported
  scenario file that does not match. Verified both directions in one run:
  real outputs ALL PASS, doctored wrong-file output FAILs on selection
  (plus the verdict recompute as second witness).
- Honest scope note: this checks the *rule*, not the *world* — if the data
  dir itself contained the wrong files, all gates would still agree with
  each other. That final mile remains human judgment (and the manifest).

## Phase 4 — Meta stack

Top finding: the gate's number rule initially criminalised entity ids —
digits inside `bridges:7` read as unverified measurements. Fixed by masking
annotated entities before the text scan, not by weakening the rule.

- `[plain]` `shapely.mapping` does not exist (same import slip as Phase 2,
  same one-line fix). Usefulness: low; notable only as a repeat — the Phase 2
  entry already paid for this lesson once.
- `[plain]` Entity-masking fix above, plus a test that asserted a filtering
  policy the extractor deliberately lacks (harvest everything, let the gate
  judge). Usefulness: medium; it pinned down the harvest-vs-judge separation
  that the whole stack relies on.
- `[hardened]` Full run G1–G11 ALL PASS, 33/33 green, numeric-aware G3 clean
  over the new `agents/` code with nothing to waive. The seed cassettes rode
  the normal manifest flow (48 files, `manifest ok`).
