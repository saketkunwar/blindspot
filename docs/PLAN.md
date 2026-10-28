# BlindSpot — Updated Plan (hardened validation, setup-first)

Status: **SETUP DONE, BUILD READY** (pending explicit `git commit` + `git tag prereg` authorization — see Gate 0).
Spec: `BUILDER_SPEC.md`. Decisions: `QUESTIONS.md` (D-1..D-6). Gates: `scripts/validate_hardened.py`, `scripts/judge.sh`.

## Goal
Qualitative space-time reasoner (RCC-8, Allen, rectangle algebra, 9-tile, distance bands) over Nepal flood + Kalimantan fire; every conclusion carries its provenance relations; independent judge checks unseen facts.

## Hardened validation (non-negotiable, fail-closed)
A phase is done only when its gates pass. **Skipped = failed.** No gate may be weakened to go green.

| Gate | Checks | When |
|---|---|---|
| G1 | `check_manifest.py` — every `data/` file listed, SHA-256 matches, kind ∈ {real,synthetic,perturbed}, real files have source+licence | setup + every phase |
| G2 | Config completeness — no `null` anywhere; ranges sane; code raises `ConfigIncomplete`, never defaults | setup + every run |
| G3 | No hardcoded answers — builder code has no scenario cell-ids/dates/filenames embedded; all params from yaml | Phase 3+ |
| G4 | Fail-closed exits — null config ⇒ non-zero exit; manifest mismatch ⇒ non-zero exit | Phase 3+ |
| G5 | CLI contract — both `python -m pipelines.* --data-dir … --out …` exit 0 (incl. `missing_input` case) | Phase 3+ |
| G6 | Output contract — §5 schemas, `inv` = exact RCC-8 inverse of `fwd`, bands valid, cells cover all dates, Act 3 honesty | Phase 3+ |
| G7 | Perturbation invariance — shifting flood +lon / FIRMS +grid & +days shifts answers identically; point order irrelevant | Phase 3+ (highest risk) |
| G8 | Data-layout conformance — flood GeoJSONs, FIRMS Layout A, timeline `start<end` | setup + Phase 3 |
| G9 | Repo hygiene — dirs present, `prereg` tag exists, config byte-identical to tag | Gate 0 + release |
| G10 | Durable tests present — `tests/properties/test_setup_invariants.py` + `test_pipeline_contract.py` kept with project | always |

Commands: `python scripts/validate_hardened.py --setup-only` (setup) · `python scripts/validate_hardened.py` (full) · `bash scripts/judge.sh` · `python -m pytest tests/properties/ -q`

## Setup (DONE — verified this session)
- [x] S-1 Installed `for-builder/` → `config/`, `scripts/`, `data/synthetic/`; created `engine/tools/ pipelines/ agents/ api/ web/ tests/properties/ data/cassettes/ results/ docs/`
- [x] S-2 Staged flood data into `data/flood_nepal/` (map in QUESTIONS.md); kept raw `data/nepflood_cascade/`; FIRMS scenario = `kalimantan_c` (Layout A documented)
- [x] S-3 Decided D-1..D-6 from rules before any pipeline run (ingest 0, min_det 3, buffer 187.5 m, evasion/cell 140.6 ha, v_max 3600 m/h, neck rule) — in `config/preregistered.yaml`
- [x] S-4 Wrote hardened harness: `scripts/validate_hardened.py` (G1–G10), `scripts/judge.sh`, durable tests in `tests/properties/`
- [x] S-5 Generated `data/MANIFEST.json` (46 files, sources/licences filled) — `manifest ok`
- [x] S-6 Verified: setup gates ALL PASS, 4/4 setup tests pass, `judge.sh` → JUDGE OK
- [ ] **Gate 0 (needs your explicit go): `git add` named files (never `blindspot-spec-kit/private/`), `git commit`, `git tag prereg`. No pipeline may run before this tag.**

## Build phases (in order, one task per run, gate after each)
- [x] Phase 1 Kernel `engine/` (DONE this run, uncommitted pending review): T-1.1 schemas (Pydantic v2, ConfigIncomplete) → T-1.2 RCC-8 exact predicates → T-1.3 composition/path-consistency → T-1.4 own Allen + 169 rectangle labels → T-1.5 9-tiles/bearing → T-1.6 Haversine/bands → T-1.7 neighbourhood graph generator in `engine/tools/`. Gate: property tests (inverse symmetry, MEETS≠BEFORE, band boundaries).
- Phase 2 Gap auditor: T-2.1 continuity/shortest-path → T-2.2 MUST_BE/MAY_BE bands → T-2.3 Detector A (rivals from t0 before t1) → T-2.4 Detector B (Allen falsification, 3 rivals, evasion D-4).
- Phase 3 Pipelines: T-3.1 loader (manifest+hash, both FIRMS layouts, select by tag/bbox) → T-3.2 flood Act1 (fwd/inv, split_alert) Act2 bands Act3 `missing_input` honesty → T-3.3 fire (floor binning, footprint RCC-8, continuity, timeline Allen). Gate: **full hardened run incl. G7 invariance.**
- Phase 4 Meta `agents/`: T-4.1 SAM cassettes+`meta_usage.json` → T-4.2 three schema-validated Muse roles → T-4.3 default-deny verification gate.
- Phase 5 Serving/UI: T-5.1 FastAPI (live/cached labelled, `evidence.json`) → T-5.2 Next.js+MapLibre three-pane console.

## Risks / open
- Act 3 inputs absent → `missing_input` until supplied; never invent geometry.
- Evasion literal test unworkable (README #5) → D-4 redefinition, soft-claim risk noted.
- Pitch wording traps (MEETS, IMMEDIATE_ENVELOPE, inv-tiles) — implement per §3, fix pitch text.
- Changing config after `prereg` = new tag + full re-run. Private judge dir never enters repo.

## Success criteria
Both CLIs exit 0; full `validate_hardened.py` ALL PASS; `pytest tests/properties/` green (no skips-to-green); manifest ok; config frozen at `prereg`.
