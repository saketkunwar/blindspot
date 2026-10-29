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
