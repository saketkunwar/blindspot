# BlindSpot — Comprehensive Phase Documentation

Companion to [BUILDER_SPEC.md](../BUILDER_SPEC.md) (what to build),
[PLAN.md](./PLAN.md) (order and gates), [QUESTIONS.md](../QUESTIONS.md)
(decisions and findings), and [PROGRESS_ERROR.md](../PROGRESS_ERROR.md)
(what verification caught, per phase). Code and tests are the primary record;
this file explains the *why* behind each phase: objectives, design decisions,
algorithms, verification evidence, incidents, and limitations.

- [Phase 0 — Setup and hardened validation harness](#phase-0--setup-and-hardened-validation-harness)
- [Phase 1 — Qualitative kernel](#phase-1--qualitative-kernel)
- [Phase 2 — Gap auditor](#phase-2--gap-auditor-upcoming)
- [Phase 3 — Pipelines](#phase-3--pipelines-upcoming)
- [Phase 4 — Meta stack](#phase-4--meta-stack-upcoming)
- [Phase 5 — Serving and UI](#phase-5--serving-and-ui-upcoming)

## Phase 0 — Setup and hardened validation harness

Committed as `c3c5606`, tagged `prereg`. Nothing analytical was built; the
goal was a frozen, verifiable foundation so no later result can be accused of
moving the goalposts.

### Objectives

1. Install the `for-builder/` skeleton (`config/`, `scripts/`,
   `data/synthetic/`) into the repo without touching `private/`.
2. Stage raw data into the spec layout (`data/flood_nepal/`,
   `data/fire_kalimantan/`) with every mapping written down.
3. Decide all six `null` config values from rules — never from demo cells —
   and freeze them under the `prereg` tag before any pipeline runs.
4. Build the hardened gates (G1–G10), the local `judge.sh`, and the first
   durable tests, so every later phase has a machine-enforced definition of
   done.

### Data staging map

Raw sources are kept untouched under `data/nepflood_cascade/` (flood) and
`data/fire_kalimantan/` (FIRMS exports); the spec layout holds staged copies:

| Spec path | Source | Content |
|---|---|---|
| `data/flood_nepal/flood_extent.geojson` | sep9 `hot_flood_npl_flood_extent.geojson` | 1 polygon |
| `data/flood_nepal/bridges.geojson` | sep9 `hot_flood_npl_bridges_osm.geojson` | 171 linestrings |
| `data/flood_nepal/hydropowers.geojson` | sep9 `hot_flood_npl_exposed_hydropowers.geojson` | 10 points |
| `data/flood_nepal/helipads.geojson` | sep9 `hot_flood_npl_helipads_osm.geojson` | 14 mixed |
| `data/flood_nepal/waterways.geojson` | sep9 `hot_flood_npl_waterways_osm.geojson` | 400 mixed |
| `data/flood_nepal/destroyed_before.geojson` | sep9 destroyed-features | 2841 features |
| `data/flood_nepal/destroyed_after.geojson` | sep14 destroyed-features | 3965 features |
| `data/fire_kalimantan/*.json` | 13 FIRMS exports, kept as-is | scenario file = `kalimantan_c` tag |
| `data/synthetic/operator_timeline.json` | for-builder fixture | 2 phases + 1 claim |

The scenario FIRMS file uses Layout A:
`{tag, bbox, day_range, detections:[{lat, lon, valid_time,
payload:{acq_date, …}}]}`. Date for binning: `payload.acq_date`. Other files
use Layout A for other regions, Layout B (bare list with
`latitude/longitude/acq_date`), or are empty — the Phase 3 loader must handle
all three and select by tag/bbox, never by filename or directory order.

### Config decisions (frozen at `prereg`)

| ID | Key | Value | Rule |
|---|---|---|---|
| D-1 | `tolerance.ingest_deg` | `0` | Source coords carry 5 decimals; not grid-rounded, so exact predicates |
| D-2 | `fire.min_detections` | `3` | FIRMS noise rule: 1–2 detections = noise, ≥3 = presence |
| D-3 | `fire.footprint_buffer_m` | `187.5` | Half a VIIRS pixel (375 m / 2) |
| D-4 | `fire.evasion_ha_per_cell` | `140.6` | 10 VIIRS pixels (10 × 14.06 ha), just under the 150 ha total, so ≥2 capped cells can jointly evade |
| D-5 | `flood.v_max_m_per_hr` | `3600` | 1 m/s riverine flood-wave celerity, conservative upper bound |
| D-6 | `flood.neck_rule` | north/south split | Neck = waterways intersecting the flood extent; upstream = outside extent north of flood centroid; downstream = south (Nepal drains south) |

Full rationale lives in `QUESTIONS.md`. After `prereg`, changing any value
requires a new tag plus a full re-run of both pipelines and all gates.

### Hardened gates (G1–G10)

| Gate | Enforces | Runs |
|---|---|---|
| G1 manifest integrity | every `data/` file listed, SHA-256 match, kind/source present | always |
| G2 config completeness | no `null`; ranges sane; code raises `ConfigIncomplete` | always |
| G3 no hardcoded answers | no scenario cell-ids/dates/filenames in builder code | full |
| G4 fail-closed exits | null config / corrupt manifest ⇒ non-zero exit | full |
| G5 pipeline CLI contract | both CLIs exit 0 incl. `missing_input` | full |
| G6 output contract | §5 schemas, exact fwd/inv inverses, Act 3 honesty | full |
| G7 perturbation invariance | shifted data ⇒ identically shifted answers | full |
| G8 data-layout conformance | flood/FIRMS/timeline shapes | always |
| G9 repo hygiene | dirs present, `prereg` exists, config frozen | always |
| G10 durable tests present | the suite ships with the project | always |

Entry points: `python scripts/validate_hardened.py --setup-only` (setup),
`python scripts/validate_hardened.py` (full), `bash scripts/judge.sh`
(mirrors the external judge's order). G4–G7 and the pipeline-contract tests
are correctly red/blocked until Phase 3 — that blocking is the harness
working, not a failure.

### Verification evidence (observed)

- `validate_hardened.py --setup-only` → ALL PASS (G1, G2, G8, G9, G10).
- `data/MANIFEST.json`: 46 files, `check_manifest.py` prints `manifest ok`.
- `test_setup_invariants.py`: 4 passed (config ranges, manifest hashes,
  FIRMS layout, flood files + timeline `start<end` with the MEETS fixture).

### Limitations and open items

- `barrier_lake.geojson` and `sar_anomaly_union.geojson` do not exist: Act 3
  will report `missing_input` until they arrive; no geometry is ever invented.
- No `AGENTS.md` was supplied with the spec kit; a minimal one was created
  pointing at the spec and plan (owner to confirm).
- Scoreboard/"Paper §13" numbers are not produced by this repo; they come
  from the judge's `evidence.json`.

## Phase 1 — Qualitative kernel

Committed as `d21ac46` (on top of setup `c3c5606`, tag `prereg`). Implements
spec tasks T-1.1–T-1.7 with no scenario knowledge anywhere in `engine/`
(G3-clean by construction).

### T-1.1 Schemas (`engine/schemas.py`)

Strict Pydantic v2 models (`extra="forbid"` on every model): `Rcc8Value`,
`Snapshot` (the §5 output contract: `rcc8`, 2-label `rectangle`, `tiles`,
`bearing`, `edge_gap_m`, `centroid_dist_km`, `band`), `Hypothesis`,
`DetectorVerdict`, plus pipeline-facing `State`, `Transition`, `GapReceipt`,
`Insight`. `load_preregistered()` raises `ConfigIncomplete` on any `null`
anywhere in the config — code downstream never substitutes a default.

### T-1.2 RCC-8 (`engine/qstr_core.py::rcc8`)

Exact Shapely predicates applied in a fixed order: empty → error; `equals`
→ EQ; `disjoint` → DC; `touches` → EC; `contains_properly` → NTPPi;
`contains` → TPPi; reverse pair → NTPP/TPP; otherwise PO. Any coordinate
tolerance is applied once at ingestion (config), never here. Snapshot
direction follows the spec: `snapshot(A, B)` reads "A rel B", and every pair
is emitted as `fwd = snapshot(feature, reference)` plus `inv`, the exact
inverse in every layer.

### T-1.4 Rectangle algebra (same module)

`allen(a0, a1, b0, b1)` is hand-written from endpoints only with day-resolution
half-open semantics: an end equal to the other's start is MEETS, never BEFORE.
The 13×13 composition table is **generated, not transcribed**: at import,
every weak order of the six endpoints (ranks 1–6, 46656 assignments) is
enumerated and each satisfiable `(r1, r2) → r3` triple recorded. This is exact
because every model induces a weak order and every weak order is realised by
ranks. `rectangle_label` applies Allen per MBR axis (169 labels);
`compose_rectangles` composes axis-wise. Degenerate (point/line) MBR axes are
expanded by `MBR_EPS_DEG = 1e-9`, a documented numerical guard — not a
coordinate tolerance, which stays exactly what the config says.

### T-1.3 Composition and propagation (`engine/propagation.py`)

The RCC-8 8×8 table is transcribed from the published RCC-8 table (Wikipedia
"Region connection calculus", Randell/Cui/Cohn lineage) and verified in-test
by converse symmetry over all 64 cells, EQ identity laws, and the worked
example TPP;EC = {DC, EC}. Transcription incident: rows were initially
zipped against `RCC8_RELATIONS` (where EQ sorts 4th) instead of table order,
silently shifting every row after PO — the durable tests caught it before any
downstream use; the fix is an explicit `_TABLE_ORDER` with a comment
(see `PROGRESS_ERROR.md`). `path_consistency_with` is a directed PC-2
worklist over ordered pairs (reverse pairs always hold the exact converse
set); `network_status` labels each pair ENTAILED (one relation left),
POSSIBLE (several), or CONTRADICTION (none).

### T-1.5 Tiles and bearing (same module)

`tiles_of` returns the set of the reference MBR frame's 9 tiles the other MBR
touches, with closed edges counting on both sides (a bridge exactly on the
edge touches both tiles). `bearing_word` gives the 8-wind compass direction
of A seen from the reference (`"O"` when coincident).

### T-1.6 Distance (same module)

`edge_gap_m` is 0 when connected, otherwise Shapely distance after projecting
both geometries to latitude-corrected planar metres at the mean centroid
latitude. `centroid_dist_km` is Haversine. `band_for` reads limits only from
config: CONTACT (gap 0), IMMEDIATE_ENVELOPE (0 < gap < envelope),
NEAR (< near km), MEDIUM (< medium km), FAR (otherwise).

### T-1.7 Neighborhood graph (`engine/tools/`, `engine/neighborhood.py`)

Derived, not hand-written. `generate_neighborhood.py` runs two merged
mechanical enumerations (single-enum derivation provably misses edges — see
incident below) and writes `engine/neighborhood.json`; `neighborhood.py`
loads it and answers adjacency plus shortest missing-state paths for T-2.1.

Deformation rules (both enums): S and S′ stay edge-connected (splitting and
teleport growth are discontinuous), growth adds a cell edge-adjacent to S,
and the toggled cell never CROSSES the reference boundary (meeting both
interior and exterior). A crossing cell teleports across the contact instant
(e.g. DC straight to PO), skipping the state any continuous path must pass
through — hence teleport jumps are absent from the graph:

| | Edges (symmetric) |
|---|---|
| Textbook 8, all witnessed | DC-EC, EC-PO, PO-TPP, PO-TPPi, TPP-NTPP, TPPi-NTPPi, TPP-EQ, TPPi-EQ |
| Genuine extra, kept with evidence | PO↔NTPPi (hole-closing: continuous at the completion instant) |
| Teleport jumps, verified absent | DC↔PO, PO↔DC, NTPP↔DC, NTPP↔PO, EC↔NTPP, DC↔EQ, … |

Evidence: 18 directed edges from 17,102 witnessed toggles
(`witness_counts` in the JSON). Enum A (corner 3×3 reference, 17-cell
universe) witnesses DC-EC via a far disjoint staging cell and TPP-NTPP via
the strictly-inside centre cell; Enum B (centre 2×2 in full 4×4) witnesses
the strict-containment-outside family NTPPi, which a corner reference cannot
surround. The generator fails loudly (`SystemExit`) if any textbook edge is
unwitnessed.

### Verification evidence (observed)

- `tests/properties/test_kernel_invariants.py`: 12 passed — Allen 13
  relations + MEETS fixture, Allen/RCC-8 converse symmetry + identity +
  spot checks, path-consistency refine + contradict, snapshot inverse over
  synthetic shapes, all-nine-tiles inverse case, bands built from live config
  thresholds (no literals), real flood data over all 195 bridge/hydropower/
  helipad features (fwd/inv inverse, Schema-valid), config fail-closed.
- Hardened: setup gates still ALL PASS; G3 manual scan on `engine/` clean.
- Incidents: table zip-order bug, swapped converse assertion (test-side),
  single-enum shortfall — all in `PROGRESS_ERROR.md` with `[plain]` /
  `[hardened]` tags.

### Limitations

- Degenerate MBR axes use the 1e-9 guard; boundary-exact pathological cases
  (a point exactly on an MBR edge) take the expanded-axis label.
- PO↔NTPPi is a deliberate superset of the commonly drawn 8-edge diagram;
  it is continuous (argued in the generator docstring) and errs toward fewer
  false violation flags on noisy daily data.
- The kernel knows no scenarios: no filenames, dates, counts, or cell ids
  appear in `engine/`.

## Phase 2 — Gap auditor

Uncommitted pending review. `engine/gap_auditor.py` turns kernel relations
into gap reasoning (spec T-2.1–T-2.4); no scenario literals appear in the
module (G3-clean; all thresholds come from the passed-in `cfg`).

### T-2.1 Continuity

`check_continuity(entity, from_date, to_date, from_rel, to_rel)` returns a
`Transition`: repeats and neighborhood steps are CONTINUOUS; anything else is
a DISCONTINUOUS_JUMP whose `missing_intermediates` is the shortest
neighborhood path between the states (endpoints exclusive), e.g. NTPP→DC
reports `["TPP", "PO", "EC"]`. `continuity_series` maps consecutive
(date, relation) pairs (the per-cell input Phase 3 will feed it).

### T-2.2 Blind-spot bands

`blind_spot_bands(last_geom, gap_hours, v_max_m_per_hr)` returns GeoJSON
`must_be`/`may_be` plus `radius_m = v_max * hours`. MUST_BE is the last known
geometry itself — the minimum claimable without an extra drainage rate;
MAY_BE buffers it by the expansion radius (local equirectangular projection,
same constants as the kernel). `classify_assets` splits `(id, layer, geom)`
assets into inside-band (with their rcc8, anything but DC) and outside, which
is exactly the Act 2 asset listing.

### T-2.3 Detector A (hydrological dipole)

`split_reaches` implements D-6 verbatim: features intersecting the flood
extent are the neck; the rest split by centroid latitude against the flood
centroid (north = upstream, south = downstream). Hypothesis-before-data is
structural, not procedural: `predict_a_rivals(up_t0, down_t0)` takes only t0
areas — there is no parameter for t1 — and `judge_detector_a` evaluates the
t1 areas against them. Opposite-sign change beyond a 1%-of-scale epsilon
(upstream gain + downstream loss) triggers impoundment SUPPORTED / free
drainage FALSIFIED; decisive non-dipole change does the reverse; negligible
change leaves both OPEN.

### T-2.4 Detector B (alibi evasion)

`detector_b(detections, claim, cfg)` takes `(date, cell_id)` pairs and the
timeline claim. Falsification uses Allen overlap: a detection day `[d, d+1)`
falsifies iff `allen` against the claim is not `b/m/mi/bi` (mere touching at
the boundary does not falsify). Rivals: extinction (nothing on/after claim),
smoldering (claim-window detections in known cells), boundary-hopping
(claim-window detections in new cells). Evasion groups cells into
4-connected components on the tenth-degree grid; a component triggers when
its summed `detections × viirs_pixel_area_ha` exceeds `evasion_ha_total`
while every cell stays below `evasion_ha_per_cell` (full-period totals per
D-4). `triggered` means an evasive patch was found; the claim verdict rides
along as its own hypothesis.

### Verification evidence (observed)

- `tests/properties/test_gap_auditor.py`: 6 passed — jump path NTPP→DC,
  DC→PO missing `[EC]`, band radius from live config, asset split, D-6
  north/south buckets, rivals OPEN-before-data then dipole/non-dipole/null
  judgments, falsification + three rivals on synthetic detections, evasion
  firing on two adjacent below-cap cells but not on one lumped cell (counts
  derived from config, no literals).
- Hardened: setup gates still ALL PASS (22/22 runnable durable tests),
  G3 scan clean.

### Limitations

- MUST_BE = last-known geometry is the only defensible minimum without a
  drainage/decay rate; if Phase 3 needs contraction semantics it must come
  back as a config decision, not a code tweak.
- Evasion connectivity is 4-neighbourhood on the tenth-degree cell grid;
  diagonal-only contact does not connect.
- `triggered` for Detector B means evasion found, not claim falsified; the
  pipeline surfaces both separately.

## Phase 3 — Pipelines

Uncommitted pending review. `pipelines/loader.py` + two CLIs. This phase
unlocked the full hardened run for the first time: G1–G10 ALL PASS, 25/25
durable tests green, plus a rigid-shift probe mirroring the perturbation
design (all pass, worst float deviation 8.9e-10 at a 1e-6 bar).

### T-3.1 Loader (`pipelines/loader.py`)

`load_manifest` + `verify_path` raise `ManifestError` on unlisted files, hash
mismatches, or bad kinds; every file a pipeline reads contributes a
`{file, sha256, kind}` inputs entry. GeoJSON features parse to Shapely with
the ingest tolerance applied once at ingestion (no-op at D-1 = 0; defined as
coordinate snapping when non-zero). FIRMS parsing handles all observed
layouts: Layout A dicts (`{lat, lon, valid_time, payload:{acq_date}}` — note
the date lives in `payload`, a layout detail any shift harness must respect,
see Limitations), Layout B bare lists (`latitude/longitude/acq_date`), and
empty lists. Records merge `properties` with `payload` fallbacks, and output
is sorted for determinism under point reordering.

Scenario selection is data-driven, never by filename: the timeline's `site`
string is matched against FIRMS `tag`s (the scenario file carries the site
name); fallback is most detections inside the timeline window, then most
overall. Documented here so the rule can be audited.

### T-3.2 Flood (`pipelines/flood_secondary_dam.py`)

Act 1 snapshots every bridge/hydropower/helipad against the flood extent
(`<layer>:<index>` ids), `split_alert` = exact-RCC-8 vs MBR separation
disagreement (INV-SPLIT). Act 2 builds MUST_BE/MAY_BE along the waterway
union for `blind_window_hours` and lists assets in/out of MAY_BE (195/195 in
with the frozen 172.8 km radius — honest consequence of D-5, not tuning).
Act 3: the optional `barrier_lake.geojson` / `sar_anomaly_union.geojson` are
absent, so `status: missing_input` with both listed, null union snapshot, and
an untriggered Detector A whose evidence still reports the computed
per-reach destroyed areas (t0/t1, D-6 zones, m2) — reported, not invented.
Exit 0 throughout; exit 1 on manifest/IO failure, 2 on incomplete config.
`--fast-cache` reuses the output only when recorded input hashes match.

### T-3.3 Fire (`pipelines/fire_peat_evasion.py`)

Floor-binned 0.5-degree cells (`"<lon>,<lat>"` SW-corner ids), zero-filled
counts for all five dates (09-16 to 09-20), 30 cells, 6142 detections total —
the anchor cell reproduces the filed total and day counts from the data
itself. Footprints: per cell per day, union-find clusters over a spatial
hash (link < 2x buffer), qualifying clusters (at least `min_detections`)
touching the cell form the footprint; RCC-8 vs the cell polygon, DC when
none qualifies. Continuity per consecutive date pair; all six ordered
timeline relations (m and o where the pitch wording disputes them — endpoints
win); claim verdict by Allen overlap (falsified: 846 detections on 09-20);
Detector B from the auditor. Shift-invariance holds by construction: rigid
date/coordinate shifts move cells, dates, relations, verdicts, and trigger
identically (probe evidence above); input point order cannot leak through
(sorted parse, sorted outputs).

### Verification evidence (observed)

- Full `validate_hardened.py`: G1–G10 ALL PASS, including first-ever G3/G4/G5/G6.
- `pytest tests/properties/`: 25 passed (setup 4, kernel 12, auditor 6,
  pipeline contract 3 — flood inverse/missing-input, fire coverage,
  fire-shift, point-order).
- `/tmp/shift_probe2.py` (throwaway, not committed): flood ids/snapshots at
  1e-6, flood act3, fire cells/dates/claims/timeline/detector_b — ALL PASS.
- Incidents: payload-date parse miss (Layout A dates live in `payload`;
  caught by zero-cell output, fixed with merge fallback); probe strictness
  (exact float equality too tight for Haversine — matched to the 1e-6 bar).

### Limitations

- FIRMS dates live in `payload.acq_date`; any external shift harness must
  shift that field (not just top-level date keys) for the timeline-shift leg
  to stay consistent — stated here so it can be adapted, not silently
  assumed.
- Act 2 MAY_BE radius (172.8 km) puts every asset inside; narrowing it needs
  a config change post-`prereg`, i.e. a new tag and full re-run.
- Footprint RCC-8 series follow the T-3.3 rule mechanically; several cells
  differ from the pitch's illustrative sequences — data plus frozen rule win
  (those expectations are soft).

## Phase 4 — Meta stack

Uncommitted pending review. `agents/` holds perception, abduction, and the
default-deny gate (T-4.1–T-4.3). No live model is called anywhere: every role
is deterministic, schema-validated, and tested, with the same interfaces a
model-backed version would satisfy.

### T-4.1 Perception (`agents/sam_perception.py`)

`perceive(image_ref, prompt)` serves SAM 3.1 masks offline-first: disk cache
(`results/sam_cache/<sha256>.json`, outside the manifest) → recorded
cassette (`data/cassettes/<sha256>.json`, manifested as synthetic) → loud
`CassetteMiss` (never an invented mask). The cache key is the SHA-256 of the
canonical request JSON; each cache entry and the two seed cassettes carry
timestamps. Every call — hit or miss — appends `{ts, request_hash, model,
hit, source, n_polygons}` to `meta_usage.json` (git-ignored by design, as a
run log, not a deliverable). Masks are GeoJSON polygons returned as Shapely
geometries.

### T-4.2 Abductor (`agents/muse_abductor.py`, `agents/ledger.py`)

Three single-turn, Pydantic-validated roles with no loop or hidden state:
`extract_claims` harvests per-sentence `Claim`s (entities, RCC-8 codes,
numbers) from prose; `write_rivals` frames the canonical rival set per
scenario (fire: extinction/smoldering/boundary-hopping/evasion; flood:
free_drainage/impoundment — predicates live in the auditor, this role only
names what to test); `write_brief` composes annotated `Statement`s whose
every number, relation, and entity the gate can check. `build_ledger`
collects the verified fact set from both pipeline outputs plus the timeline:
observed RCC-8/Allen/rectangle labels, all walked numbers, and every feature,
cell, claim, site, scenario, and layer id.

### T-4.3 Verification gate (`agents/verification_gate.py`)

Default deny. `check(brief, ledger, mode)` validates each statement's
annotations against the ledger, then scans the masked text (annotated entity
ids blanked out, so digits inside `bridges:7` or `10.0,0.0` are not claims)
for RCC-8 codes, quoted Allen codes, and numbers — every text number must be
annotated and ledger-true. Strip mode drops offending statements with
reasons; block mode rejects the brief on the first violation. An empty ledger
verifies nothing, so all numeric statements strip out and the brief comes
back number-free, per spec. ISO dates and bare years are carved out of the
number rule (documented).

### Verification evidence (observed)

- `tests/properties/test_meta_stack.py`: 6 passed — cassette hit → cache
  hit → polygons, miss raises and still logs, seeds loadable and
  hash-addressed, roles schema-validated, verified statement kept while an
  invented entity/relation/number/unannotated-number statement is stripped
  (4 violations) and blocked, empty ledger yields an empty brief.
- Hardened: full run G1–G11 ALL PASS; G3 (now numeric-aware) clean over
  `agents/`; 33/33 durable tests green.
- Incidents: `shapely.mapping` does not exist (fixed import); digits inside
  entity ids tripped the number rule (fixed by entity masking, not by
  weakening the rule); extractor test initially asserted a filtering policy
  the extractor deliberately does not have (harvest vs judge separation
  clarified). All in `PROGRESS_ERROR.md`.

### Limitations

- No live SAM transport exists in this build; a present API key is logged but
  cannot conjure a transport — a miss is still a miss. Wiring a real endpoint
  later changes only the last branch of `perceive`.
- The abductor roles are deterministic framings, not a language model; they
  satisfy the single-turn schema-validated contract but do not generate free
  prose.
- The gate checks annotated ids and codes, not open-vocabulary name
  resolution ("the big bridge" is unverifiable by design).

## Phase 5 — Serving and UI (upcoming)

`api/server.py` (FastAPI, live/cached labels, `evidence.json`) and `web/`
(Next.js + MapLibre three-pane console). Docs to add: endpoint table with
example responses, console pane map, live-vs-cached semantics.
