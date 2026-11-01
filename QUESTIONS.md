# QUESTIONS.md — decisions, unknowns, data findings (append-only)

> Rule: a `null` config, missing file, or undocumented layout is **reported here**, never guessed in code.
> Config decisions D-1..D-6 were frozen before any pipeline run, from rules — not from demo-cell results.

## Config decisions (frozen at tag `prereg`)

| ID | Key | Value | Rule (decided before seeing results) |
|---|---|---|---|
| D-1 | `tolerance.ingest_deg` | `0` | FIRMS/GeoJSON coords carry 5 decimals (e.g. `112.45574`); not grid-rounded. Exact predicates. |
| D-2 | `fire.min_detections` | `3` | FIRMS noise rule: isolated 1–2 detections treated as noise; a connected cluster of ≥3 counts as presence. |
| D-3 | `fire.footprint_buffer_m` | `187.5` | Half a VIIRS pixel (375 m / 2), per README-FIRST guidance. |
| D-4 | `fire.evasion_ha_per_cell` | `140.6` | 10 VIIRS pixels (10 × 14.06 ha), just below `evasion_ha_total` (150) so ≥2 connected cells each below cap can sum past total. Redefines the unworkable literal test (README problem 5: 25 detections ≈ 350 ha). Evaluated over the full period per T-2.4 wording. |
| D-5 | `flood.v_max_m_per_hr` | `3600` | 1 m/s riverine flood-wave celerity — conservative upper bound for MAY_BE expansion over the 48 h blind window. |
| D-6 | `flood.neck_rule` | see yaml | Nepal rivers drain south: neck = waterways intersecting flood extent; upstream = outside extent, north of flood centroid; downstream = outside extent, south of centroid. Deterministic, no hand-picked points. |

After `prereg`, changing any value requires a new tag + full re-run of both pipelines + all hardened gates.

## Data findings (inspected, not guessed)

### FIRMS — `data/fire_kalimantan/firms_kalimantan_c.json` (the Kalimantan scenario file)
- Layout A (dict): `{tag, bbox, day_range, fetched_at, detections:[{lat, lon, valid_time, payload:{acq_date, acq_time, satellite, instrument, confidence, frp, ...}}]}`.
- Scenario file identified by `tag == "kalimantan_c"`, `bbox [112.0,-3.0,115.0,0.0]`, 5 days, VIIRS only.
- Date for binning: `payload.acq_date` (equals `valid_time` date). Lon/lat: `lon`/`lat` at detection top level.
- Other files in `data/fire_kalimantan/` use Layout A (other regions) or Layout B (bare list `[{latitude, longitude, acq_date, ...}]`) or are empty. Loader must handle both layouts and select the scenario file by tag/bbox — never by file order. See hardened gate G-7.

### Flood — `data/flood_nepal/` (staged from `data/nepflood_cascade/flood_data_processed_sep9/`)
| Spec file | Source | Geometry |
|---|---|---|
| `flood_extent.geojson` | `hot_flood_npl_flood_extent.geojson` | 1 × Polygon |
| `bridges.geojson` | `hot_flood_npl_bridges_osm.geojson` | 171 × LineString |
| `hydropowers.geojson` | `hot_flood_npl_exposed_hydropowers.geojson` | 10 × Point |
| `helipads.geojson` | `hot_flood_npl_helipads_osm.geojson` | 14 × mixed |
| `waterways.geojson` | `hot_flood_npl_waterways_osm.geojson` | 400 × mixed |
| `destroyed_before.geojson` | sep9 `hot_flood_npl_destroyed_features_osm.geojson` | 2841 |
| `destroyed_after.geojson` | sep14 `hot_flood_npl_destroyed_features_osm.geojson` | 3965 |

Raw sources kept untouched under `data/nepflood_cascade/` and listed in the manifest.

## Open / missing (do not invent)

- `flood_nepal/barrier_lake.geojson`, `flood_nepal/sar_anomaly_union.geojson`: **absent**. Act 3 must report `status:"missing_input"`, list both, exit 0.
- `AGENTS.md`: spec says "Read AGENTS.md first" but none was supplied. A minimal one is created in setup pointing at `BUILDER_SPEC.md`; owner to confirm.
- Gemini pitch wording conflicts (data wins): Mobilization/Clearing is MEETS not BEFORE; <50 m gap is IMMEDIATE_ENVELOPE not NEAR; "all 9 tiles" is `inv` direction. Implement per BUILDER_SPEC §3.
- Scoreboard/"Paper §13" numbers: not produced by this repo; come from judge `evidence.json`.

## Phase 1 verification notes (kernel, this run)
- RCC-8 composition table transcribed from Wikipedia "Region connection calculus" (Randell/Cui/Cohn lineage); self-checks in-test: converse symmetry over all 64 cells, EQ identity, worked example TPP;EC = {DC, EC}. Allen composition is NOT transcribed — it is generated at import by exhaustive 6-endpoint order enumeration (exact by order-isomorphism), with identity/spot/converse checks in-test.
- Transcription incident caught by the durable tests: table rows were zipped against `RCC8_RELATIONS` (EQ sorts 4th) instead of table order; fixed with an explicit `_TABLE_ORDER` + comment. This is the workflow working as designed.
- Neighborhood graph derived by `engine/tools/generate_neighborhood.py` (two enums merged, 4.6k+ toggles witnessed): textbook 8 edges all present; extras PO<->NTPPi (hole-closing, continuous at the completion instant) kept as evidence; teleport jumps (DC<->PO, NTPP<->DC, ...) absent. Artifact: `engine/neighborhood.json`.
- G3 manual scan on `engine/`: no hardcoded scenario literals.

## Spec-literal hygiene
Builder code must never contain expected counts/distances/cell ids from any pitch text. Enforced by gate G-3 (see `docs/PLAN.md`, `scripts/validate_hardened.py`).

## Phase 3 loader findings (T-3.1)
- Layout A detection dates live in `payload.acq_date` (top level has only
  `valid_time`). Any external harness that shifts dates must shift the
  payload field; top-level date keys do not exist on these records.
- Scenario-file selection is data-driven: timeline `site` string matched
  against FIRMS `tag` (case-insensitive containment), fallback most
  detections inside the timeline window, then most overall. No filename or
  count is embedded in code.

## Phase 4 cassette format (T-4.1)
- `data/cassettes/<sha256(request)>.json` holds `{"request": {image, prompt,
  model}, "response": {"masks": [GeoJSON Polygon/MultiPolygon...],
  "recorded_at": ...}}`. Two seed fixtures ship (flood chip, fire chip).
- Runtime cache lives in `results/sam_cache/` (outside the manifest);
  `meta_usage.json` is a git-ignored run log at the repo root.

## Demo Step-0 source notes (2026-10-28)
- T1/T2 from the cascade file's own interval ends: T1 = 2026-09-04T03:56:20Z
  (earliest end; cutoff = min end), T2 = 2026-09-09 (two boundaries that day).
  2092 / 754 / 1568 features per group. T3 bound fenced, not load-bearing.
- Flood extent is static ("Observed 27 August") — no time signal; change
  evidence comes from damage geometry only.
- Chilime Khola present in staged waterways (2 pieces of 400 named 38).
- Model: 1.2-Contributor primary (shipped 5 Aug 2026 pre-flood; independent
  probes measure effective knowledge late 2025/Jan 2026; Meta publishes no
  cutoff). Fallback 1.3-Contributor + anonymization (shipped Sep 2026).
  Live probe (`demo/nepal_cascade/probe_model.py`) pending key; symbolic
  path shipped (zero model memory).
- Web: Chilime/secondary-dam reporting confirms a real barrier-lake burst
  narrative post-cutoff — that is GT, quarantined, never in prompts.
- Open: live 1.2 call recording; T3 exact bound; presentation manual
  open-and-look against the live page.

## Demo live-call results (2026-10-28, key provided by user)
- Endpoint found by user pointer: Meta Model API docs (dev.meta.ai) give
  base `https://api.meta.ai`, key as `MODEL_API_KEY` Bearer, model id
  `muse-spark-1.2-contributor` listed. Transport speaks chat-completions.
- The provided `LLM|...` key authenticates on api.meta.ai (it failed on
  api.llama.com: empty model list, all names invalid — wrong endpoint, not
  a bad key). Never written to disk; passed via env only.
- Step-0 probe (`demo/nepal_cascade/probe_result.json`, live-recorded):
  flood question -> "I have no knowledge of this." Control -> cutoff stated
  as January 4, 2026. Verdict: CLEAN (empirical, not just structural).
- Insight model round (cassette `87d24316...`, live-recorded): the clean
  model ranks `safe_drainage` first from the anonymized evidence while the
  symbolic ledger scores burst highest (0.94). Disagreement recorded as
  `agreement:false` — the model reasoned, not recalled. Frozen probabilities
  are symbolic-only by design; the model round is advisory and gate-checked.

## Setup-round results (2026-10-28, three live rounds on 1.2-Contributor)
- R1 (ledger only): generic M_fluvial/M_null/M_other, no flood physics.
- R2 (+ flood ontology): all six flood stories adopted; rejected on
  abbreviated fact ids (30+ cite errors).
- R3 (+ cite-format line): valid, null PASS; same stories, timid cluster
  weight (0.5 vs frozen 2.0) -> draft top downstream-only, burst 4th.
  Cluster threshold 34 likely anchored on the ledger's reported count
  (frozen-rule parameter leak into setup input, not GT leak).
- Standing: LLM frames vocabulary, human sets conviction, kernel computes.

## P2 readings (2026-10-29, user-approved before build)
- No WATERSHED.permanent_id / reach_code keys exist in any data file
  (OSM tags only), so "replace the static network" is implemented as
  spatial reach codes from geometry only: target (near target reach),
  else upstream/downstream of the flood-centroid latitude. Distances
  reuse the domain's channel-adjacent value; no new constants.
- FHZ gate is structural, deliberately: families present/computable
  per zone (fail-closed only on missing counterparts). No
  non-disjointness gate — 113 of 418 real zones are disjoint from both
  outline and assets (remote wet network); failing them would mistake
  geography for broken plumbing. Informativeness is diagnostics.
- E/R/G = extent-topological (RCC-8 vs outline), reach-directional
  (tiles + bearing vs flood centroid), group-containment (RCC-8 vs
  evidence union). Meta-vocabulary = ledger fact ids + mechanism ids
  (the citable set). Stories: supports/opposes over real ids,
  non-empty supports, weighted null story.

## P0 verification fix (2026-10-28)
- `demo/nepal_cascade/inputs/waterways.geojson` carries a provenance date in one `source` value (`Digital Globe,2015-05-03` on `way/343295489`). Curation copies waterways verbatim, so the Context Card inventory saw an ISO date.
- `agents/context_card.py::build_card` treated any ISO date in the inventory as contamination and aborted (`SystemExit`), failing 3/3 card tests. Per `docs/FLEX_NS_PLAN.md` Step 3 the card must redact dates from prompt text, not crash on provenance metadata.
- Fix: redact ISO substrings in value labels to `[date]` before building the card; fail-closed guard now checks the redacted card. `card_text` verified date-free by the durable tests.

## Demo 2 validation checks (2026-10-29, human framing)
- The worry was fair: a system that grades its own homework is not
  validation. So the Kalimantan fire study holds out real ground truth in
  two independent ways, and the brief must still point at the right
  outcome without ever seeing the held-out part.
- Temporal check: the ledger only sees FIRMS detections up to 2026-09-20.
  Everything after that date (the late-September restart) is locked away.
  Computed top mechanism is suppression_then_restart at 0.84 support
  (second: continued_spread at 0.11). The pre-cutoff pattern — a clean
  multi-day gap followed by an unbroken run — already favours
  "suppression wins, then peat restarts", which is exactly what the
  held-out days confirm. Pass.
- Spatial check: same frozen rules, but the eastern half of the map is
  masked out (3,071 of 6,142 detections kept, west of median longitude).
  Ranking is unchanged: suppression_then_restart still top at 0.84. The
  probabilities are identical to four decimals because scoring depends
  only on which facts are active, not their magnitudes — every gate still
  passes on half the map, which is itself the finding: the fire signal is
  spatially pervasive, not driven by one hotspot. Pass.
- Engine honesty note: building the fire study exposed three gaps that
  turned out to be engine limitations, not fire-specific needs, so they
  were fixed in the closed op set and pinned by durable tests
  (tests/properties/test_fact_generics.py): cluster can count against a
  scoped cell list (ref_role/ref_filter), time_stats accepts a scale
  divisor (seconds to days), and weights live inside facts entries so no
  parallel block can drift. Flood regression is byte-clean
  (top=impoundment_then_burst 0.9426, gate ALL PASS, judge 95 passed).

## Demo 2 setup round result (2026-10-29, live key)
- The model, shown only the pre-cutoff ledger, drafted six fire
  mechanisms with real weights, passed the null test, and disagreed with
  the human rules on top exactly the way the plan predicts for LLM
  framing without conviction. It put the most weight on the unbroken run
  (0.95) and hotspot clumping (0.9) — the same two facts the frozen brief
  leans on. Criterion: setup drafts for both domains pass the null
  red-team — now satisfied for fire as well as flood.

## Raw data registry claims (2026-10-29, operator-confirm pending)
- `data/raw/REGISTRY.json` registers all 934 raw files under 12 entries
  (G18 watches both directions). Every licence below is the assistant's
  reading from filenames/export conventions, written explicitly for
  correction — none is confirmed:
- ems_data_sep9 + emsr927: Copernicus EMS Rapid Mapping activation
  EMSR927 grading products (GRA_28xx, Langtang corridor); claimed
  licence: Copernicus free/full/open with attribution.
- flood_data_processed + 4 dated siblings: HOT/OSM/Overture/Tasking
  Manager exports, operator-processed; claimed ODbL-1.0 (OSM-derived)
  + CDLA-Permissive-2.0 (Overture).
- temporal_data split per file: osm_temporal_cascades ODbL-1.0;
  bipad_/dhm_ captures as-published with no explicit licence stated;
  candidate_spatial_association as project-internal.

## Memory M1 read-path values (2026-10-30, decided before any memory-adjusted brief)
- `config/preregistered_memory.yaml` v2 keeps `rule_id: restart-noisefloor-v1`
  (M0 episode/outcome values untouched) and adds: signature count bins
  `[1, 3, 10, 100, 1000, 10000]` (coarse on purpose — fine bins would leave
  every pattern with a history of one); `min_episodes_to_speak: 5` (smallest
  count at which a smoothed rate means anything; current census of 2 stays
  silent); `smoothing_alpha: 1.0`, `max_abs_shift: 0.10` (a nudge, never a
  veto); `outcome_supports` for the fire domain only (restart backs
  suppression-then-restart; quiet backs stay-out/burn-out stories; flood has
  no episodes so no mapping is claimed there).
- Openbearing on the plan's flagged judgement call: the outcome labelling
  rule itself (`restart-noisefloor-v1`, M0) is still the operator's to
  confirm or revise — everything downstream re-runs deterministically if it
  changes, under a new rule id.

## Memory v3 values + M3 scoping (2026-10-30, decided before first M2/M3 runs)
- `null_test`: seed 7, 200 trials, histories of 8, frozen shape
  [0.4, 0.3, 0.2, 0.1] (a four-story ranking with a clear but fallible
  favorite; truth drawn from the frozen distribution). `max_null_edge:
  0.02` (shuffled labels must not beat frozen — expectation is a loss,
  since chasing noise costs); `min_signal_edge: 0.05` (perfect-signal
  labels must gain clearly — the positive control). First run observed
  −0.130 / +0.270: both margins hold with room to spare, no tuning.
- `evolver`: one proposal per run, recurrence bar 3, independence gap 2
  days (neighboring slides share most data), propose/validate split
  0.4/0.4 of the observed span with the final fifth never touched,
  win margin 0.05 with both frozen tops kept, Track B opens weight-only.
- Scoping calls: candidates (issue + evidence, no complete change) exist
  as a distinct status because the deterministic analyzer cannot author
  fixes — they can never be approved, which G22 pins. The cassette layer
  reports no token counts, so traces record response length instead of
  inventing one. Flood has no episodes, so the Skeptic's episode replay is
  fire-only today; the frozen-top check covers whichever study's rules
  change. M4 stays parked with P4 (no production stream, no daemon).

## Signature too fine — fix pending operator decision (2026-10-30)
- The all-scenes census (48 episodes, 26 labelled, 11 scenes) groups into
  48 patterns of one: `FF2`/`FF5` gap dicts (growing counts/spans) and the
  raw `FF6` area float pass through the signature verbatim and fingerprint
  every slice, so no pattern reaches the speaking threshold of 5.
- Proposed v4 fix (NOT applied): project gap dicts to (binned day-gap,
  binned distinct-day count), drop `FF6` from the key or log-bin it
  (it is documented context-only with no time signal). Applying this
  changes preregistered values: needs a config version bump, a full
  backtest re-run, and re-verification of G19/G20/G24 before any brief
  reads the new key. Awaiting your go.
- Secondary observation, no action: all 26 labels are restart (one
  September season, no quiet window); memory could only reinforce the
  frozen top until some scene goes quiet.

## Signature fix approved and applied (2026-10-30)
- You approved the v4 key as proposed: gap dicts project to binned
  day-gap plus binned distinct days, raw floats leave the key. Applied in
  `engine/memory.py` + config v4 with a new signature test; backtest
  re-run reproduces all 48 episode rows byte-identically. Result: 22
  patterns, strongest at 4 labelled — still silent, threshold untouched.
  Integral-area flicker (dropped vs binned by floating-point exactness)
  noted in `docs/MEMORY.md` as the next key revision's problem.

## Morning-brief triggers (2026-10-31, preregistered before the runner exists)
- The daily fire agent (`collab_agent/`) studies the fresh pull only when
  a trigger fires; otherwise it logs one quiet line. Priority order:
  (c) labelled count reaches 5, (b) unseen signature, (a) count spike,
  (d) quiet after a matched window. Reasons:
- (a) Spike: today >= 2x the trailing 4-day median. Two is the smallest
  multiple that the October pull (476 vs a 12-25 baseline) clears
  unambiguously; a lower bar would page the operator on noise, and the
  FIRMS noise floor is 1-2 isolated detections.
- (b) New shape: live signature matches no stored pattern. A shape the
  archive has never seen is definitionally worth one study; no tuning
  involved, exact signature-id match only.
- (c) Memory speaks: labelled count under the live signature reaches 5.
  This is the milestone the whole memory arc waits for; the brief gains
  its second ranking that morning.
- (d) Quiet after match: yesterday's pull sat in a matched pattern and
  today brings < 3 detections. Three mirrors the hotspot rule's own
  floor (clumped >= 3); below it the window may label quiet once its
  outcome window closes — never the same morning.
- Changing any threshold later is a versioned config amendment with the
  reason recorded here, never a quiet retune.

## Cross-region diagnosis (2026-10-31, before any new download)
- Recomputed from `results/memory_episodes.sqlite3` under the v4 key: 22
  patterns, 13 single-scene, 9 cross-scene. Leader (4 labelled / 6 eps):
  5x Iberia + 1x Texas. Runner-up (4/4): Cerrado only. Third (3/3):
  Amazon + W.USA + Kalimantan — three continents, one shape.
- Download list this evidence supports: extend Iberia and Texas windows
  (the leader needs one more labelled case), plus one quiet window for
  a matched box (the missing arm). No new regions: different fuels add
  patterns of one, and the key is strict on purpose.
- Success reads: 5th label (memory speaks, before/after brief as demo),
  pattern break (regionality finding, same weight), first quiet label
  (missing arm exercised). All read as-is; rule and key stay frozen.

## Recall tier (2026-10-31, operator decision: counts are not a memory)
- The counts-only memory stood accused, fairly, of being a lookup table
  rather than recollection. New bottom tier `engine/memory.py::nearest_cases`:
  given a window's facts, return the top_k nearest labelled past windows
  (scene, cutoff, outcome window, label, detections before/after, frozen top
  story), ordered by signature-fact difference count, ties on episode id.
- Distance counts differing facts (shared fact in another bin, or a fact
  one side lacks); every step away is named in `differing` so the operator
  sees HOW a case differs, not just that it does.
- Same as-of discipline as the pattern table: only outcome windows closed
  on/before as_of are shown. Same-shape windows with no usable label yet
  are counted (`unlabelled_same_shape`), never displayed as known — this
  is where the missing quiet case stays visible instead of buried.
- Preregistered as `recall: {top_k: 5}` under memory config version 5
  (reading-only addition; episode/outcome rows untouched, v4 re-run check
  still stands). Changing top_k later is a versioned amendment.
- Scope held: brief-level memory (autoinsight note + adjust math) is
  untouched, so G19/G20-pinned briefs do not move. Recall first appears in
  the Demo-2 snapshots (study-shaped and live-shaped queries) and pages.

## Model-swap comparison (live run, operator key via env)
- Fire setup re-run under challenger `muse-spark-1.3-contributor` (--no-card,
  out-dir /tmp, 4 new cassettes manifested as real): null PASS, 0 citation
  errors, top `M1_smolder_restart`, top_agrees False — mirroring the recorded
  1.2 round (null PASS, 0 errors, top `smoldering_restart`, agrees False).
  Frozen brief byte-identical across the run. Probe reported the challenger
  knowledge-clean first. Finding: swapping the framing mind moves the frozen
  ledger by 0.0000; the harness discriminates identically across the family.
- The pasted chat key is exposed: rotate it. No key material in cassettes,
  usage log, or repo (scanned before manifesting).

## Third mind: muse-wonder-1.0 (live run, same key, same discipline)
- Fire setup under `muse-wonder-1.0` (--no-card, /tmp, 4 new cassettes
  manifested as real): probe clean, null PASS, 0 citation errors, top
  `persistent_smoldering_in_hot_cells`, top_agrees False. Weights agree with
  both predecessors on the top-two facts (FF4 0.95, FF5 0.9; 1.2 had them
  0.9/0.95, 1.3 the same pair). Frozen brief byte-identical across all three
  minds. Showcase beat updated from two minds to three; finding unchanged:
  the framing mind never moves the ledger.
