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
