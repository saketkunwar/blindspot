# Flexible, Truly Neurosymbolic Pipeline — Concrete Plan

Reviewed and concretised from the flexibility sketch in chat. Scope:
generalise the flood autoinsight demo into a study pipeline where a new
domain (fire, earthquake, industrial leak, …) requires **zero code
changes** — only a domain config, curated data, and recorded cassettes.
The flood demo stays frozen and becomes the regression baseline: its
brief must reproduce byte-identically after every refactor.

## Review of the sketch (what held up, what was missing)

Held up: domain config owns vocabulary; ontology authoring is a human
sign-off, not an LLM guess; geometry fallbacks must leave the code;
fail-closed setup gate for new domains. Missing, now fixed below:
(1) the sketch let the setup LLM *name* facts but gave the kernel no way
to *compute* them on a new domain — concretised as a closed fact-catalog
(Step 1); (2) no proof the refactor preserves flood behaviour —
concretised as parity gates (Steps 1–2); (3) "flexible" was untestable —
concretised as a second-domain acceptance test with a zero-code-change
rule (Step 6); (4) redaction and date-leakage rules were vague —
concretised in the Context Card spec (Step 3).

## Target architecture

Three rounds, one frozen contract. Neural output is always typed JSON,
always validated or rejected; symbolic code never imports model output
into probabilities.

1. **Setup round (LLM frames).** Context Card (pre-cutoff aggregates
   only, redacted tokens, no raw coordinates, no ground truth) → draft
   study: mechanisms, fact selections (catalog op + params), thresholds,
   weights, priors, cluster rule. Validators: cites ⊆ catalog, quiet
   story present (domain keywords), priors bounded, null-test pass,
   non-degeneracy (no story > 0.98 or below uniform under the real
   ledger). Human reviews and freezes; the LLM never auto-freezes.
2. **Compute round (QSTR computes).** Fact-catalog evaluated on curated
   inputs → ledger → documented scores → softmax → `brief.json`
   (same output schema as the flood brief, domain-agnostic).
3. **Rank round (LLM advises, unchanged from the flood demo).**
   Anonymized prompt, gate-checked cites, advisory only.

### Domain contract: `demo/<study>/domain.json`

The only domain-specific artifact. Code knows how to frame a study;
this file says which world we are in.

```json
{
  "domain_id": "river_valley_flood",
  "ontology": "…vocabulary text: processes this domain admits, incl. the quiet story; vocabulary, not evidence…",
  "cutoff": {"rule": "earliest_end", "time_field": "destruction_interval_end"},
  "inputs": [
    {"role": "damage", "path": "inputs/damage.geojson", "kind": "featurecollection"},
    {"role": "network", "path": "inputs/network.geojson", "kind": "featurecollection"},
    {"role": "boundary", "path": "inputs/boundary.geojson", "kind": "featurecollection"}
  ],
  "target": {"role": "network", "name_field": "name", "values_from": "setup"},
  "geometry": {"channel_adjacent_m": 250, "cluster": {"distance_m": 500, "min_features": 8}},
  "quiet_keywords": ["nothing", "quiescen", "null", "baseline", "no_further"]
}
```

Curation is driven by this file: select the pre-cutoff slice by `cutoff`,
strip time fields, write `inputs/` + `input_audit.json` (per-file SHA-256,
derived cutoff value, counts). No filename, date, threshold, or vocabulary
in code.

### Fact catalog (closed op set, `engine/facts.py`)

Each op is a pure function `(inputs_by_role, params) -> (value, active)`;
thresholds come from the draft, never from code. New ops are the only
allowed extension point and require tests + rationale in PROGRESS_ERROR.

| Op | Meaning | Flood use | Fire use |
|---|---|---|---|
| `count` | features in role | F1 total damage | detections total |
| `near_share` | share of role A within D m of role B | F3 channel-adjacent | — |
| `half_share` | share on one side of a bearing split at a reference centroid | F2/F5 upstream | — |
| `cluster` | (count, hit) of role A within D of target subset of B | F4/F7 tributary | — |
| `area_sum` / `area_mean` | polygon areas | F6 extent context | footprint area |
| `time_stats` | distinct times, max gap, span over a time field | — | F-analogues |
| `spread` | bbox extents of a role | diagnostics | diagnostics |

## Steps

- **Step 0 — Baseline freeze (no code).** Record SHA-256 of the flood
  `brief.json`, `rules.json`, prompt artifacts, and setup reports.
  Hand-write `demo/nepal_cascade/domain.json` from the frozen rules.
  Acceptance: checksums file committed; flood briefly described as Study 1.
- **Step 1 — Fact catalog.** Implement `engine/facts.py` + unit tests.
  Acceptance (parity): catalog reproduces the flood ledger exactly —
  F1 = 2092, F2 ≈ 0.515, F3 ≈ 0.728, F4 hit with 34, F5 ≈ 1.061,
  F7 ≈ 0.016 — from the curated inputs and flood `domain.json`.
- **Step 2 — Ledger extraction.** Move `compute_ledger`/`score_mechanisms`
  from `agents/autoinsight.py` into `engine/`; flood imports the engine
  versions (move, not duplicate). Acceptance: flood brief byte-identical
  to the Step-0 checksum; G12 + full judge green.
- **Step 3 — Context Card.** `agents/context_card.py`: reads `domain.json`
  + curated inputs, emits card text + `card.json` (hash-logged). Contains
  per-role counts, geometry-type mix, property-key inventory (keys and
  value *types* only), low-cardinality value labels (≤ 50 distinct),
  pre-cutoff time range. Place names → `T-1…T-n` tokens with the map kept
  outside the prompt; dates → relative snapshot labels. Acceptance test:
  flood card contains no place-name token and no ISO date string
  (enforced by the same input-derived token audit as the ranking round).
- **Step 4 — Generic setup.** Rewrite `agents/setup_study.py`: ontology,
  instruction framing, geometry defaults, input paths, quiet keywords,
  and fact ids all come from `domain.json` / the card; code keeps only
  the loop (prompt → validate → null-test → compare). Flood dogfood:
  draft from the flood card, compared qualitatively against the frozen
  rules. Acceptance: valid draft + null-test pass. **Agreement with the
  frozen study is explicitly not required** — the round-3 disagreement
  (timid cluster weight) is preserved in the report as the expected
  signature of LLM framing without conviction.
- **Step 5 — Freeze flow.** `scripts/freeze_study.py`: draft → `rules.json`
  (copy, never in-place edit), pins card + prompt + draft hashes, prints
  the `git tag study/<domain>/v1` command for human approval. Any later
  edit = new version directory, full re-run.
- **Step 6 — Demo 2 proves flexibility (Kalimantan fire study).**
  Author `demo/fire_study/domain.json` (FIRMS detections, cells,
  timeline roles), curate, setup round on 1.2-Contributor with the same
  cleanliness rules, freeze, compute, presentation section on the demo
  page. Acceptance: **zero edits to `engine/` or `agents/` after the
  Step-4 commit.** If an edit is forced, it must be a new catalog op with
  tests + a PROGRESS_ERROR entry naming it a catalog gap; more than one
  such gap fails the step and the catalog is redesigned before Demo 3.
- **Step 7 — Hardened gates + docs.** Add to `scripts/validate_hardened.py`:
  - **G13 (domain generic):** `domain.json` schema-valid; setup-prompt
    audit clean against card tokens; cards for every study contain no
    place names / ISO dates.
  - **G3b (no domain vocabulary in code):** rare tokens (len ≥ 6,
    stopword-filtered) extracted from each study's `ontology` must be
    absent from `engine/` + `agents/` source. This makes "flexible"
    machine-checked instead of asserted.
  - **G14 (study reproducibility):** setup replay from cassettes
    reproduces draft hashes; compute replay reproduces briefs
    byte-identically (G12 generalised to every frozen study).
  - **G15 (mutable null):** per frozen study — all facts zeroed ⇒ quiet
    story top; all facts active ⇒ top ≠ quiet (documented exception
    allowed, named in the study README).
  Update `docs/PHASES.md` (flexible-pipeline section),
  `PROGRESS_ERROR.md` (per-step `[plain]`/`[hardened]` entries), and
  `USAGE_DEMO.md` (DEMO 2 replay instructions).

## Validation plan

- Per step: its acceptance gate above, plus `scripts/validate_hardened.py`
  (ALL PASS incl. new gates), `python -m pytest tests/properties/ -q`,
  `bash scripts/judge.sh`, `cd web && npm run build`.
- Highest-risk check: **flood brief byte-identical** at Steps 2, 4, and 7
  (the regression baseline). Any diff stops the line; the refactor is
  wrong, not the baseline.
- Flexibility evidence for the final report: git log showing Demo 2
  touched only `demo/fire_study/`, `data/` (cassettes/manifest), and
  docs — no `engine/`/`agents/` paths.

## Risks / open questions

- **Catalog creep.** Mitigation: closed op set; per-op test + rationale;
  the Step-6 one-gap rule forces redesign discussion instead of silent
  growth.
- **Conviction still human.** Setup LLM proposes weights; freeze is a
  human act. Automating weight conviction is out of scope until a
  proposal passes G15 on both studies and a human signs the tag.
- **Context-Card leakage.** Pre-cutoff slice only; value labels capped;
  token audit + G13. Residual: property *keys* reveal domain semantics
  (e.g. a stage field name) — accepted as data-dictionary context, the
  same a human analyst receives, and recorded here as a known surface.
- **Ontology regress.** `domain.json` is human-owned. An LLM may draft
  one from a data inventory, but the file ships only with human
  sign-off; "this is a flood study, not fire" is user context, and
  laundering it through the model would be theater.

## Success criteria

1. Flood brief byte-identical after the refactor (baseline preserved).
2. Fire Demo 2 runs end-to-end with zero `engine/`/`agents/` edits after
   Step 4 (config + data + cassettes only).
3. G1–G15 ALL PASS; durable suite green; judge OK; web build clean.
4. Setup drafts for both domains pass the null red-team with their own
   weights.
5. No ontology vocabulary in builder code (G3b) — flexibility is a gate,
   not a claim.

