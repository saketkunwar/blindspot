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

## Phase 5 — Serving and UI

Top finding: nothing fought back — the first full-stack phase with no
incidents, which itself says something about the harness: by Phase 5 the
gates and suite catch integration mistakes before they reach the report.

- `[plain]` One self-caught sloppy assertion (a `startswith` prefix check
  where an exact scenario match belonged) fixed before the first run.
  Usefulness: low; pride, mostly.
- `[hardened]` Full run G1–G11 ALL PASS, 37/37 green, numeric-aware G3 clean
  over `api/` + `web/`, production `next build` compiling clean. The API's
  honesty cases (400 on bad mode, 404 on absent evidence) are tested, not
  just coded.

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

## Demo — Nepal cascade autoinsight

Top finding: the honest density fix mattered — the first upstream/downstream
density ratio came out 313269x because region areas were feature areas, not
ground areas. A plain eyeball caught it; the frozen number is now a sane
1.06x, and burst support comes from the cluster hit plus channel adjacency,
not from a bug.

- `[plain]` Prompt-anonymity check initially allowed counts freely, which
  risked year-like 4-digit evidence (2092) tripping a naive year denylist.
  Fixed by deriving forbidden date strings from the inputs themselves
  (exact strings + prefixes) instead of numeric ranges. Usefulness: medium;
  precision beats paranoia in a gate.
- `[plain]` Probabilities rounded to 4dp summed to 1.0001, failing the
  plan's own "sums to 1" contract. Fixed in the artifact (largest-residual
  correction on the top entry), not in the test tolerance. Usefulness:
  medium; the output contract is the deliverable.
- `[plain]` G12's hide-raw step failed cross-device (`/tmp` vs the media
  mount). Fixed by hiding in place (`data/raw_hidden_for_g12`) with a
  leftover guard and `finally` restore. Usefulness: low; plumbing.
- `[hardened]` Full run G1–G12 ALL PASS, 43/43 green (37 old + 6 new),
  `judge.sh` OK, `next build` clean with the new `/demo/nepal-cascade`
  route. G12 proves the prediction reads no post-cutoff byte (hidden-raw
  re-run byte-identical); the quarantine half proves curated inputs carry no
  timestamps/stages and the verbatim prompt re-scans clean. The null
  red-team test (quiet synthetic world ranks nothing-first) is the gate that
  proves the outcome was not pre-loaded — the single most valuable check of
  this demo.

## Demo live call

Top finding: the knowledge-clean model disagrees with our scorer — asked
from anonymized evidence alone, 1.2-Contributor ranks safe drainage first
while the symbolic ledger puts burst at 0.94. That disagreement is the
autoinsight loop working as designed: a model with no memory of the event
reasons cautiously, the ledger scores evidence mechanically, and the brief
reports both instead of hiding the gap.

- `[plain]` The user key failed on api.llama.com (empty model list, every
  name invalid) — wrong endpoint, not a bad key. The user-pointed
  dev.meta.ai docs gave the real one (api.meta.ai, Bearer MODEL_API_KEY).
  Usefulness: high; docs beat guessing.
- `[plain]` Live backend initially assumed a bespoke prompt-in/text-out
  shape; the real API is OpenAI-style chat-completions. Rewrote to
  messages-in/choices-out with a text fallback. Usefulness: medium.
- `[hardened]` Step-0 probe empirically CLEAN (flood: "no knowledge";
  self-stated cutoff Jan 4 2026, pre-flood) and G12 now replays the
  committed live cassette, so the gate exercises the full neuro-symbolic
  path offline and deterministically. Cassettes ride the normal manifest
  flow (986 files, `manifest ok`).

## Demo cassette collision (caught by an old test, not a new one)

Top finding: the pre-existing `test_seed_cassettes_loadable` failed the
moment model cassettes landed in `data/cassettes/` — it assumes every
cassette there is a SAM mask cassette. That is exactly the kind of
cross-feature collision the durable suite exists for.

- `[hardened]` The fix was separation, not test-weakening: model cassettes
  live in `data/model_cassettes/` now, manifest re-pinned (986 files ok),
  12/12 affected tests green, G12 still ALL PASS. Usefulness: high — it
  proved the old tests guard the repo against the new code, not just the
  other way round.

## Setup round (three live rounds, one standing result)

Top finding: the LLM can frame the study but not weight it. Given flood
ontology + anonymized ledger, round 3 drafted the same six stories as the
frozen rules with same-family weights — yet cluster weight 0.5 vs frozen
2.0 puts burst 4th instead of 1st. Conviction, not vocabulary, is the human
contribution. No gaming possible: all three rounds recorded, the two
rejections (thin framing; abbreviated cites) kept as audit trail.

- `[plain]` Round-2 draft validated against full ledger ids while the model
  wrote short ones — 30+ cite errors, correctly rejected. One instruction
  line fixed it. Usefulness: high; format discipline is load-bearing.
- `[plain]` `null_test` first checked a hardcoded `no_further_event` id the
  draft never uses. Fixed to detect the quiet story by id/title keywords.
  Usefulness: medium; the harness must meet drafts on their own terms.
- `[hardened]` G1–G12 ALL PASS (989 files), 5 new offline setup tests
  green. The setup prompt re-uses the ledger-token audit; no GT strings in
  the new agents code (G3 clean).

## P0 flexible core (Steps 0–4; execution-verification pending)

Top finding: the plan's own execution exposed the environment boundary —
Steps 0–1 landed via the agent workflow (baseline freeze, fact catalog +
parity tests), Step 2's extraction landed on disk
(`engine/ledger.py`, thin `agents/autoinsight.py` CLI), and Steps 3–4
(Context Card, generic setup, freeze script) were finished inline. The
Step-2 agent stalled at the verification stage (long run, zero output
files), and this session cannot execute shell commands, so no test, gate,
or byte-diff has been observed in-session. Everything below is
static-verified only (imports resolve, names match across call sites,
rounding kept off activation boundaries); execution remains mandatory
before any done claim.

- `[plain]` Static review of the extraction: moved `compute_ledger`
  preserves fact texts/flags; catalog op rounding matches the frozen
  values with margin (F2 0.515, F3 0.728, F5 1.061, F7 0.0163 — none near
  an activation edge). Usefulness: medium; raises confidence, proves
  nothing.
- `[plain]` New surface: `agents/context_card.py` (redacted inventory +
  fail-closed on date strings), generic `agents/setup_study.py` (all
  domain words from `domain.json`, incl. new `prompt_framing`), and
  `scripts/freeze_study.py` (copy-never-edit + hash pins + human tag).
  Usefulness: pending execution.
- `[hardened]` NOT YET RUN — required before close: `pytest`
  `tests/properties/test_facts.py` `test_context_card.py`
  `test_setup_study.py` `test_demo_nepal.py`; `python -m
  agents.autoinsight --model-round on --out /tmp/p0check.json` + byte-diff
  vs `demo/nepal_cascade/output/brief.json`; full
  `scripts/validate_hardened.py` + `bash scripts/judge.sh`.

## P0 verification executed (2026-10-28)

Top finding: the P0 code was correct except one over-strict guard — the
Context Card aborted on a provenance date in the waterway metadata instead
of redacting it. One small fix, then every pending check went green.

- `[plain]` `test_context_card.py` 3/3 failed: `build_card` raised
  `SystemExit` on `'2015-05-03'` from a waterway `source` tag
  (`Digital Globe,2015-05-03`). Root cause: curation copies waterways
  verbatim (correct — it is reference geometry, not a time signal) while
  the card treated any ISO date as contamination. Fix: redact ISO
  substrings in value labels to `[date]`; guard now checks the redacted
  card. Usefulness: high; the plan (Step 3) requires redaction, not a
  crash, and the tests enforce exactly that.
- `[hardened]` P0 set 25/25 green (`test_facts`, `test_context_card`,
  `test_setup_study`, `test_demo_nepal`).
- `[hardened]` Step-2 parity: `autoinsight --model-round on` output
  byte-identical to `demo/nepal_cascade/output/brief.json`
  (top=impoundment_then_burst p=0.9426). The refactor preserves the
  frozen baseline.
- `[hardened]` Full `validate_hardened.py` ALL PASS (G1–G12);
  `judge.sh` → JUDGE OK, 62 passed. Steps 0–4 execution-verified;
  remaining P0 work is Steps 5–7 (freeze flow already on disk,
  Demo 2 fire study, gates G13/G3b/G14/G15).

## P1 API shape — versioned study reads (this run)

Top finding: the legacy demo routes already computed the right bytes, so
the v1 shape is a registry plus delegates — no recomputation paths were
duplicated, and alias parity is asserted byte-for-byte in-test.

- `[plain]` Bracket-counting by eye failed twice on the shared geo `box`
  dict (read tool renders one fewer `]` than the file holds); `grep` +
  `ast.parse` was the ground truth that settled it. Usefulness: medium;
  lesson is to verify generated-looking literals with a parser, not eyes.
- `[hardened]` New `tests/properties/test_api_v1.py` (7 tests): study
  list, brief shape + bad-mode 400, live ranking parity, legacy-alias
  byte parity (brief + geo), geo layers/cap, gt cached + live
  determinism (rerun rewrites identical bytes, committed file hash
  unchanged), unknown-id 404, `openapi.json` sync. Full gate ALL PASS
  (G3 clean with the study registry); `judge.sh` → JUDGE OK, 69 passed.

## P1 finish — store, auth, pages, rebuild (this run)

Top finding: the store caught nothing because the inputs are clean — its
value is structural (hash-pinned provenance for the next study), while
auth and the page each had one real defect class the tests now pin
(unauthed live recompute; truncated template from unbracketed string
continuation).

- `[plain]` `store/db.py` shipped with a `)`/`]` typo; the seed probe
  failed loudly on first run. Fix: one character. The page template
  silently truncated at 934 bytes (implicit string continuation does
  not span bare newlines — parenthesized the return). Both found by
  executing, never by reading. Usefulness: high for the
  execute-don't-eyeball rule.
- `[hardened]` Store: `store/schema.sql` + `store/db.py` (INSERT/SELECT
  only — no update/delete path exists), `scripts/seed_store.py`
  rebuilds `results/store.sqlite3` from frozen files (brief, gt, rules,
  inputs-audit, live cassette), `test_store.py` 6 green (deterministic
  re-seed, tamper fails, audit order).
- `[hardened]` Auth: operator token gates all live recompute (only when
  configured; unset = documented dev-open so replay stays keyless),
  per-study read tokens hashed in the store with operator bypass,
  `test_auth.py` 5 green.
- `[hardened]` Pages: `/v1/studies/{id}/page` renders hero, evidence,
  how-it-works, ranking, findings, GT, and a data-scaled SVG schematic
  from frozen bytes only (stdlib, print CSS), brief hash-checked
  against the store when seeded; `test_pages.py` 3 green.
- `[hardened]` Rebuild: `Makefile` (`install manifest gates seed api
  web judge rebuild`) + G16 (chain defined, seed deterministic,
  openapi in sync). Full gate ALL PASS; `judge.sh` → JUDGE OK,
  83 passed. Caveat: the `web` leg needs Node, which this environment
  lacks — `make rebuild`'s web step is unproven here; everything else
  ran. `results/*.sqlite3` git-ignored alongside `results/*.json`
  (derived state, same precedent).

## Web leg — CORS caught by a human (manual verification)

Top finding: every automated gate was green while the console showed
"API unreachable" in a real browser. `TestClient` does not enforce CORS,
so no gate could see it — the browser was the only oracle.

- `[plain]` Root cause: the FastAPI app had no CORS middleware, so
  `localhost:3000` fetching `localhost:8000` was blocked. Fix: allow
  cross-origin GET/OPTIONS (read-only API; live recompute stays behind
  the operator token). Pinned by a preflight + header test in
  `test_pages.py`. Lesson: serving tests need at least one Origin-header
  assertion per surface, or "served" only means "served to Python".
- `[plain]` Headless pass (chromium, software WebGL): console shell
  verified in pixels — 195 features listed from the live API, legend
  chip, status line, zoom controls, attribution all render; layout
  correct. Blank canvas under `--disable-gpu` was a harness artifact
  (no GL context), not the app. Map paint itself needs a real browser;
  tile host reachable (200). Lesson: screenshot harnesses must enable
  software GL or every canvas reads as a false failure.
- `[plain]` Genuine find from the same pass: `must_be` is a
  GeometryCollection (~418 members) — layer filters never matched it,
  so must_be clicks drew nothing. Console now flattens collection
  members to plain features; point members take band colors (circle
  paint matched by name). Verified by algorithm mirror on real
  `results/flood.json` + green build.
- `[plain]` Feature clicks showed only the generic band because act-1
  carries no geometry — but ids are `layer:index` into the source
  layers (171/14/10 = 195, exact). New read-only
  `/api/results/flood/assets` serves id-keyed geometries (no
  properties, nothing leaks); console highlights the selected asset
  in red against the band. Pinned: all 195 act-1 ids resolve.
- `[plain]` Viewport bug, caught by the user's eye: every click fitted
  the whole 172.8km may_be band (bbox 82.67–87.19°E), so the map
  showed half the Himalaya including Uttarakhand labels. The band is
  where the frozen rule puts it (centroid 84.74, 28.31, Nepal) — the
  defect was fitting the context instead of the subject. Map now fits
  the focused feature/cell with zoom capped, band stays as background.
  Lesson: plot bbox numbers of served geometries, not just their
  styling — no gate checked data extent.
- `[plain]` Default band view still framed the whole circle. The assets
  endpoint now also serves the observed flood outline as `flood-extent`
  (geometry only); band views draw band + outline and fit the outline,
  so load lands on Langtang valley with the band as background.
  Feature clicks unchanged (fit the asset).
- `[plain]` Viewport now self-reports: status line shows `N drawn ·
  z<zoom> (<lon>,<lat>)` after fitting, so the frame is checkable
  without reading tiles. Headless limit found: this sandbox proxy
  blocks the browser's style/API fetches, so map paint cannot be
  verified headless here — shell, data flow, legend, and status are
  pixel-confirmed; paint needs the real browser that already paints
  the demo.
- `[plain]` Root cause of dead bridge clicks (user-diagnosed: points
  sometimes showed, lines never did): the highlight feature carried
  no `properties.id`, so focus matching missed and the viewport fell
  back to the whole band, where a 100 m bridge line is sub-pixel.
  Points only "sometimes" showed because screen-space dots survive a
  wrong zoom. Fix: the feature id rides along on the highlight.
- `[plain]` Console map and map-legibility round (reference:
  nepflood.vercel.app structure, our numbers only): base style now
  falls back (Carto → demotiles → visible message) with tile-error
  filtering so missing tiles can't trigger style switches; layers
  styled by kind with legend chips; console pre-selects may_be and
  every click updates the map (bands → polygon, features → assessed
  band + membership row, claims → fire-cell boxes from origin +
  grid_deg); WebGL context loss shows a retry overlay instead of a
  blank pane. Stale `.next` (predating the user's `npm install`)
  500'd production serving — `rm -rf web/.next` + clean rebuild fixed
  it; dev serving had masked the rot. 20/20 serving tests green.
