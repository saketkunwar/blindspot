# BlindSpot: Builder Spec

Read `AGENTS.md` first. This file says WHAT to build. It contains no expected results on purpose.
You compute every result from the data. An independent judge checks your output against facts you cannot see.

## 1. What BlindSpot does
BlindSpot takes before and after observations of a physical system across a sensing gap (cloud cover,
an orbit gap) and finds what the gap may hide. It reasons qualitatively about space and time
(RCC-8 topology, Allen intervals, rectangle algebra, 9-tile direction, distance bands) and every
conclusion carries the relations it came from. Two scenarios: a flood (Nepal) and a peatland fire (Kalimantan).

## 2. Layout and ownership
```
engine/     schemas.py  qstr_core.py  propagation.py  gap_auditor.py      (you write)
pipelines/  flood_secondary_dam.py  fire_peat_evasion.py                   (you write)
agents/     sam_perception.py  muse_abductor.py  verification_gate.py     (you write)
api/        server.py                                                      (you write)
web/        Next.js + MapLibre console                                     (you write)
data/       flood_nepal/*.geojson  fire_kalimantan/*.json  synthetic/  cassettes/  MANIFEST.json   (read only)
config/     preregistered.yaml                                             (read only)
tests/      properties/                                                    (read only)
```

## 3. Conventions (follow exactly)
- **Snapshot direction.** `snapshot(A, B)` means: the relation of A with respect to B. RCC-8 and Allen
  labels read "A rel B". Tiles are the 9 tiles of B's MBR frame that A's MBR touches.
  For every pair, produce both `fwd = snapshot(feature, reference)` and `inv = snapshot(reference, feature)`.
  `inv` must be the exact inverse of `fwd` in every layer.
- **Allen intervals** come from endpoints only, with start < end. An end equal to the other's start is
  MEETS, never BEFORE. Dates are day-resolution, intervals half-open `[start, end)`.
- **Feature ids** are `"<layer>:<index>"`, the index being the feature's position in its file.
- **Cell ids** (fire) are `"<lon>,<lat>"` of the cell's south-west corner, each with one decimal,
  using floor binning, e.g. `"100.0,-1.5"`.
- **Bands.** `CONTACT` (gap 0), `IMMEDIATE_ENVELOPE` (0 < gap < `immediate_envelope_m`), `NEAR` (< `near_km`),
  `MEDIUM` (< `medium_km`), `FAR` (otherwise). All limits from `config/preregistered.yaml`.
- **Config.** A `null` value means "not decided". Raise `ConfigIncomplete`. Never substitute a default.
- **Manifest.** Every file you read from `data/` must be listed in that directory's `MANIFEST.json`
  and match its hash. Allowed kinds: `real`, `synthetic`, `perturbed`. Report the kind of every input you use.

## 4. Command-line contract
```
python -m pipelines.flood_secondary_dam --data-dir data --out results/flood.json [--config config/preregistered.yaml] [--fast-cache]
python -m pipelines.fire_peat_evasion   --data-dir data --out results/fire.json  [--config ...] [--fast-cache]
```
Exit 0 on success, including when an optional input is missing (report `missing_input`).
Exit non-zero on incomplete config or a manifest failure. Always read data from `--data-dir`.

## 5. Output contract
`Snapshot` = `{ "rcc8": {"relation": "DC|EC|PO|EQ|TPP|NTPP|TPPi|NTPPi", "status": "ENTAILED|POSSIBLE|CONTRADICTION"},
"rectangle": [rx, ry], "tiles": ["N", ...], "bearing": "...", "edge_gap_m": float, "centroid_dist_km": float, "band": "..." }`

`DetectorVerdict` = `{ "triggered": bool, "reason": str, "hypotheses": [{"id", "supports": [...], "refutes": [...], "status": "SUPPORTED|FALSIFIED|OPEN"}], "evidence": [...] }`

**`results/flood.json`**
```
{ "scenario": "flood_nepal",
  "inputs": [{"file", "sha256", "kind"}],
  "act1": {"features": [{"id", "layer": "bridges|hydropowers|helipads", "fwd": Snapshot, "inv": Snapshot, "split_alert": bool}]},
  "act2": {"blind_window_hours": float, "must_be": GeoJSON, "may_be": GeoJSON,
           "assets_in_may_be": [{"id", "layer", "rcc8"}], "assets_outside": [{"id", "layer"}]},
  "act3": {"status": "ok|missing_input", "missing": [str],
           "impoundment_vs_union": {"fwd": Snapshot, "inv": Snapshot} | null,
           "detector_a": DetectorVerdict} }
```
**`results/fire.json`**
```
{ "scenario": "fire_kalimantan",
  "inputs": [...], "grid_deg": float, "dates": ["YYYY-MM-DD", ...],
  "cells": [{"id", "origin": [lon, lat], "counts": {"YYYY-MM-DD": int},
             "rcc8": {"YYYY-MM-DD": "DC|..."},
             "continuity": [{"from_date", "to_date", "violation": bool, "missing_intermediates": [str]}]}],
  "timeline_relations": [{"a": "<id>", "b": "<id>", "relation": "<allen label>"}],
  "claims": [{"id", "text", "start", "end", "verdict": "falsified|not_falsified", "evidence": [...]}],
  "detector_b": DetectorVerdict }
```
Only cells that contain at least one detection need to appear. `counts` has an entry for every date in `dates`.

## 6. Tasks (do them in order; one per run)

### Phase 1: kernel (`engine/qstr_core.py`, `engine/propagation.py`, `engine/schemas.py`)
- **T-1.1 Schemas.** Strict Pydantic v2 models for States, Transitions, GapReceipts, Insights, Snapshot, DetectorVerdict.
- **T-1.2 RCC-8.** Classify a geometry pair into one of the 8 relations with exact predicates.
  Any coordinate tolerance is applied once at ingestion, from config.
- **T-1.3 Composition and propagation.** The 8x8 composition table; path consistency. One relation left is
  `ENTAILED`, several `POSSIBLE`, none `CONTRADICTION`.
- **T-1.4 Rectangle algebra.** MBRs; Allen relation on the west-east and south-north axes, 169 labels; axis-wise composition.
  Write your own Allen implementation.
- **T-1.5 Tiles.** The 9 tiles `N NE E SE S SW W NW O` from the reference MBR's edges; the set of tiles the other MBR
  touches; a centroid bearing word.
- **T-1.6 Distance.** `edge_gap_m` (latitude-corrected planar metres, nearest edges) and `centroid_dist_km` (Haversine); bands.
- **T-1.7 Neighborhood graph.** Derive it by enumerating single-cell changes over grid polygon pairs. Keep the generator in `engine/tools/`.

### Phase 2: gap auditor (`engine/gap_auditor.py`)
- **T-2.1 Continuity.** A jump between RCC-8 states that are not neighbors in the graph is a `DISCONTINUOUS_JUMP`;
  report the shortest path of missing states.
- **T-2.2 Blind-spot band.** `MUST_BE` and `MAY_BE` from the last known state, the gap duration and `v_max_m_per_hr`;
  list the assets each band touches.
- **T-2.3 Detector A (hydrological dipole).** Split a waterway into upstream, neck and downstream reaches (`neck_rule`).
  Compare area change upstream and downstream across the gap. Opposite signs support an unobserved impoundment at the neck.
  Build the rival hypotheses (free drainage vs impoundment) and their predicted relations from t0 data and config
  **before** looking at t1.
- **T-2.4 Detector B (alibi evasion).** Test a claimed cessation interval against detections with Allen relations: any detection
  inside the interval falsifies the claim. Evaluate three rivals: extinction, smoldering, boundary-hopping.
  Evasion: connected cells whose summed estimated area exceeds `evasion_ha_total` while each cell stays below `evasion_ha_per_cell`.
  Area estimate = detections x `viirs_pixel_area_ha`.

### Phase 3: pipelines
- **T-3.1 Loader.** One loader for all files: manifest and hash check, GeoJSON and FIRMS parsing, a report of each input's kind.
  The FIRMS file layout is not documented here. Inspect it, and write what you found to `QUESTIONS.md`.
- **T-3.2 Flood pipeline.**
  Act 1: from the flood extent, bridges, hydropowers and helipads, compute `fwd` and `inv` for every feature against the flood extent.
  Set `split_alert` where exact RCC-8 and the MBR verdict disagree on separation (INV-SPLIT).
  Act 2: build the blind-spot bands along the waterways for `blind_window_hours`; list assets inside `may_be` and outside it.
  Act 3: compare the two destroyed-features files (before and after). If the optional files `flood_nepal/barrier_lake.geojson` and
  `flood_nepal/sar_anomaly_union.geojson` exist, compute `impoundment_vs_union` and run Detector A. If either is missing,
  set `status: "missing_input"`, list what is missing, and do not invent geometry.
- **T-3.3 Fire pipeline.**
  Bin detections per cell per day (floor binning, `cell_deg`). Per cell per day, build the footprint: the union of detections
  (each buffered by `footprint_buffer_m`) in the connected clusters that touch the cell and hold at least `min_detections`
  detections. RCC-8 is `rcc8(footprint, cell polygon)`; no qualifying cluster gives `DC`. Compute `continuity` per cell.
  Read the operator timeline and claim from `data/synthetic/operator_timeline.json`, compute the Allen relations between
  its intervals (`timeline_relations`), test the claim, and run Detector B.

### Phase 4: Meta stack (`agents/`)
- **T-4.1 `sam_perception.py`.** SAM 3.1 through the Meta Model API; masks to Shapely polygons; cache by request hash with a timestamp;
  log each call to `meta_usage.json`. Build against `data/cassettes/`.
- **T-4.2 `muse_abductor.py`.** Three single-turn, schema-validated roles: claim extractor, rival-hypothesis writer, brief writer.
- **T-4.3 `verification_gate.py`.** Default deny. Check every relation code, number and entity name in a brief against the ledger.
  Strip or block anything not found. An empty ledger gives a brief with no numbers.

### Phase 5: serving and UI
- **T-5.1 `api/server.py`.** FastAPI. Serves results and `evidence.json`. Live and cached modes, each response labelled.
- **T-5.2 `web/`.** Three-pane console as described in the `web-console` skill.

## 7. What this spec does not tell you (do not guess)
- Missing data: the barrier-lake and SAR files may not exist. Report it.
- Config values set to `null`. Stop and report them in `QUESTIONS.md`.
- The FIRMS file layout. Inspect the file.
- Any expected count, distance, area or relation. Compute it.
