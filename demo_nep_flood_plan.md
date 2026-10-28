# Demo Nepal Flood — Autoinsight Plan

## Goal

Build `demo/nepal_cascade/`: a clean, self-contained Nepal flood demo plus an
autoinsight pipeline that discovers possible outcomes from pre-cutoff data
only. The pipeline scores an open set of mechanisms — including
"nothing further happens" with real weight — and outputs support-strength
probabilities. The actual event is the ground truth (GT) used *only* afterward
to check the ranking. Nothing about the GT may leak into the prediction run:
no post-cutoff bytes, no tuned rules, no pre-loaded answer. The result is
presented in the web app as a public-facing demo page modeled on the
reference layout (hero → evidence cards → how-it-works → mechanism ranking →
findings → legend map), with every number rendered from demo output.

## Success Criteria

- The demo runs end to end from `demo/nepal_cascade/` on curated inputs plus
  the frozen kernel, auditor, and gate code. No new science code is invented
  for the demo; only wiring, rules, and tests.
- Prediction inputs are provably pre-T1 (2026-09-04): every input byte is
  hash-pinned to manifest entries dated ≤ T1, and the run's input audit is
  published with the output.
- The mechanism set is fixed before running, contains at least five distinct
  outcomes including an explicit no-further-event hypothesis, and the output
  probabilities sum to 1. The pipeline is *capable* of ranking
  no-further-event first; a run where the burst story cannot lose is a failed
  run by definition.
- The GT check (T1→T2 delta: 754 newly destroyed features; Sep-7 SAR lake
  log) is evaluated only after the prediction is frozen, and the report states
  plainly whether the top-ranked mechanism matched, with no re-tuning.
- Full hardened gates green; G3 clean over all new code; no GT strings,
  dates, counts, or place-names from the verification side appear in pipeline
  or demo code.
- The demo presentation page renders from demo output via the API (mode
  labelled), with mechanism probabilities, findings counters, and legend map
  all present; no value on the page exists anywhere as a literal in `web/`.

## Approach

**Time model (verified against the data).** The cascade file gives three
interval groups: destroyed_pre_T1 (2,092), T1→T2 Sep 4→9 (754), T2→T3
(1,568). The prediction world is pre-T1 only; the GT is the T1→T2 delta plus
the Sep-7 SAR lake log (3.4 km², between the snapshots). The flood outline is
static ("Observed 27 August") and carries no time signal; all change evidence
comes from damage geometry and relations. The Sep-14 file is a later damage
state, not the burst date — the demo does not claim otherwise.

**Open mechanism set (fixed pre-run, frozen like config).** At least:
safe drainage, dam holds stable, impoundment→burst, upstream slope failure
elsewhere, downstream-only flooding, no-further-event. Each is scored for and
against by ledger evidence (dipole stats, continuity jumps, cluster hits,
SAR-log-free reasoning — the SAR log is GT-side, never prediction-side).
Scores normalize to probabilities explicitly labeled *support strength, not
calibrated frequency*: "how strongly the pre-cutoff data supports each
story," never weather-forecast percentages.

**Chilime Khola cluster (the overfitting trap, defused).** The 12-of-400
segment claim is tested as one frozen rule applied once: the cluster
definition (connectivity, distance to waterway, per-khola grouping) is
written and committed before the run, then evaluated against the named
Chilime Khola pieces in our waterways. Match or mismatch is reported
as-is; the rule is never adjusted to fit. With 400 segments, chance clusters
are expected — the frozen rule is what separates a test from a story.

**Neuro-symbolic loop, hindsight-free.** Kernel first (per-snapshot
relations, reach-split dipole, continuity — all pre-T1), ledger diff across
the pre-T1 world, rival framing from t0-style data, then the model proposes
ranked mechanisms citing ledger facts, then the verification gate admits only
ledger-grounded claims (bounded revision rounds). The model prompt never
contains post-cutoff bytes; the cutoff gate proves it by perturbation.

**Contamination verification (how "autoinsight" is proven, not sloganed).**
Outputs are probabilities over stories; inputs may never assert an outcome.
Five checks, all fail-closed:
1. **Prompt construction by type.** The prompt builder takes only the ledger
   (pre-cutoff aggregates). There is no parameter for GT text, outcomes, or
   later dates — leaking the future is a type error, not a discipline
   problem (the Detector A pattern, extended).
2. **Outcome-free instruction.** Fixed instruction text: *"Here is evidence.
   Here are the candidate mechanisms. What does the evidence support, and
   why?"* Mechanism labels are hypotheses to score, never facts to explain.
3. **Anonymized context.** Prediction-round prompts carry no place names,
   no calendar dates — relative snapshots and anonymous reaches — so the
   model's own training memory cannot key on the event. Real names return
   only at presentation time, after the prediction is frozen.
4. **Prompt audit gate.** Every prompt is saved verbatim as a run artifact;
   a deny-list scans for post-cutoff dates, GT filenames, and
   outcome-asserting phrases. Any hit fails the run.
5. **Memory-free rounds + null red-team.** Each model call is single-turn
   with no history; the full prompt history is the audit log. Before the
   real demo, the same pipeline runs a quiet synthetic case: if
   "nothing happens" does not rank first there, the outcome was pre-loaded
   somewhere and we find out before it matters.

**Model transport.** Prediction runs on
`muse-spark-1.2-contributor` *if* Step 0 confirms it is both available and
knowledge-clean: Meta publishes no cutoff for either Contributor SKU, but
independent probes measure Spark 1.2's effective knowledge at late 2025 /
January 2026 — before the August 2026 flood — so a clean 1.2 structurally
cannot recall the event. Confirmation is empirical, not taken from docs:
ask the model directly about the flood and about other post-cutoff events;
any real answer = contaminated = excluded. Fallback is
`muse-spark-1.3-contributor` with strictly anonymized prompts (its
knowledge may include the event; anonymization is the only defense), and
the swap is recorded, never silent. Transport itself is a new
`agents/model_call.py`: request-hash cassette record/replay (extending the
Phase-4 pattern), usage logging with model id and tier, live calls only
with explicit flag plus key, default runs replay-or-record-once.
Contributor constraints are structural: public OSM/FIRMS aggregates only in
prompts (training-on-data tier), no `max` effort (unavailable on
Contributor anyway).

**Presentation (reference-inspected, this run).** The demo page mirrors the
reference layout — hero title and corridor line, evidence cards (sensors
and sources with their areas), a three-step how-it-works (Detect → Classify
→ Cascade), findings counters, map legend, and the map — but renders only
values produced by *our* pipeline for *this* demo: mechanism probability
ranking, verdict-gated brief text, and the demo's own counts. The reference
site's figures are never copied; they are a layout guide, not data. Content
flows `demo output → GET /api/demo/nepal-cascade → presentation page`, mode
labelled like every other endpoint. The three-pane console stays as the
operator view; the presentation page is the public view. Styling follows the
taste preflight (flat panels, restrained accent, no gradients or glow), not
the reference's emoji-card style.

## Steps

1. **Step 0 — close the source gaps (research, no code). DONE 2026-10-28.** Confirmed from the cascade file itself: T1 = 2026-09-04T03:56:20Z, T2 = 2026-09-09 (two boundaries that day), derived as earliest/latest interval ends — no date was typed into prediction code. The T2→T3 bound stays fenced (not load-bearing). Chilime Khola exists in staged waterways (2 pieces of 400). Model: `muse-spark-1.2-contributor` primary on structural evidence (shipped 5 Aug 2026; independent probes measure effective knowledge late 2025/Jan 2026, pre-flood); `probe_model.py` ships for live confirmation when a key exists; until then the frozen prediction runs the symbolic path (no model memory at all). Confirm or bound
   the T3 date from the sep10/sep29 passes; pull the NDRRMA mid-September
   SitReps and the IRDR 18–19-hour dam analysis for the narrative fence.
   Probe `muse-spark-1.2-contributor` availability and knowledge (direct
   post-cutoff questions; any real answer excludes it). Record in
   `QUESTIONS.md`. The demo narrative says only what this step confirms,
   and the model choice is frozen here, before any insight run.
2. **Demo directory.** `demo/nepal_cascade/` with curated inputs (pre-T1
   cascade view, static extent, waterways, Chilime subset), manifest
   additions with kinds preserved, and a README stating the confirmed
   timeline and the open questions. Reuse `pipelines/loader.py`; add
   `--as-of` snapshot filtering plus a published input audit (file → hash).
3. **Frozen rules.** Mechanism set, scoring weights, and the Chilime cluster
   rule written, reviewed, and committed before any insight run — same
   discipline as the `prereg` tag. Changing a rule after seeing output
   requires a new tag and full re-run.
4. **Insight loop (`agents/autoinsight.py`).** Pre-T1 kernel pass → ledger
   diff → rival framing → model rounds with ledger context → gate → brief
   with mechanism probabilities. GT files are unreadable from this path by
   construction (separate input root; the run fails if a GT hash appears in
   its inputs).
5. **Transport + cassettes.** `agents/model_call.py`, one recorded live call
   (key + flag), replay determinism check, usage log entry.
6. **Gates.** G12 cutoff-invariance (delete/perturb all post-T1 data ⇒
   byte-identical insight), GT-quarantine audit (run inputs ∩ GT files = ∅),
   G3 clean, full suite + `judge.sh` green.
7. **Demo API + presentation.** `GET /api/demo/nepal-cascade` serving demo
   output with mode label; presentation route in `web/` rendering hero,
   evidence cards, how-it-works, mechanism ranking, findings counters, and
   legend map from that payload. Filters (by mechanism, by risk band) if the
   payload supports them without new computation in the browser.
8. **Docs.** `docs/PHASES.md` demo section, `PROGRESS_ERROR.md` entry with
   `[plain]`/`[hardened]` tags, `QUESTIONS.md` source notes.

## Validation Plan

- `python scripts/validate_hardened.py` ALL PASS including G12 and the
  quarantine audit; `pytest tests/properties/ -q` green.
- Highest-risk check, in two halves: (a) cutoff proof — insight at
  `--as-of 2026-09-04`, then delete/perturb every post-T1 file and re-run
  for byte-identical output; (b) GT check — frozen prediction vs the T1→T2
  delta and SAR log, reporting rank of the true outcome with no re-tuning
  allowed afterward.
- Model path: cassette replay green without a key; one live call logged with
  hash; replay determinism check.
- Presentation: `npm run build` clean; the rendered page contains hero,
  evidence cards, how-it-works, mechanism ranking, findings, and legend —
  all from a live API payload (cached mode); manual open-and-look to confirm
  layout order and map fit (no headless browser in this environment).
- Manual: read the final brief against the Step-0 source notes — every
  historical claim traces to a cited source or a ledger fact, and the word
  "burst" appears only with its evidence attached.

## Risks / Open Questions

- **T3's exact bound is unverified** (sep10/sep29 passes exist; Step 0 pins
  which bound the T2→T3 group corresponds to). The demo's core claim needs
  only T1/T2, so this is fenced, not blocking.
- **The 12-segment cluster may not reproduce** under a frozen rule — that is
  a finding, not a failure, and the report must present it as one.
- **Support-strength probabilities are uncalibrated** by construction; the
  brief labels them as such. Any reader wanting frequencies is told plainly
  they do not exist yet.
- **Contributor tier trains on prompts** — acceptable for public aggregates;
  nothing else is sent. Assumption; override if any prompt content must stay
  private.
- **Presentation drift risk:** the reference page's style invites copying its
  numbers (sensor areas, feature counts). The page renders only demo-output
  values; any literal in `web/` beyond the existing bundle fails G3.

## Sources

- [telegraph.com/nepal-tibet-glacier-flood-new-lake-dam-bhote-koshi](https://telegraph.com/nepal-tibet-glacier-flood-new-lake-dam-bhote-koshi/) — first dam broke, second dam built, ~2M m³ lake, explicit uncertainty about catastrophic burst (inspected, non-empty, fetched this run)
- [lirneasia.net/2026/10/nepals-bhotekoshi-disaster-every-link-existed-nothing-joined-them](https://lirneasia.net/2026/10/nepals-bhotekoshi-disaster-every-link-existed-nothing-joined-them/) — 26 Aug collapse timeline, 27 Aug barrier-lake warning, 28 Aug overflow and rescue pause, Chilime Khola as damage site (inspected, non-empty, fetched this run)
- [orcarouter.ai/blog/muse-api](https://www.orcarouter.ai/blog/muse-api) — Contributor model IDs, tier pricing/training trade, no-`max`-on-Contributor (inspected, non-empty, fetched this run)
- [llm-stats.com/models/compare/muse-spark-1.2-vs-muse-spark-1.3](https://llm-stats.com/models/compare/muse-spark-1.2-vs-muse-spark-1.3) — no published knowledge cutoff for 1.2 or 1.3; [github.com/apoorvumang/knowledge-cutoff](https://github.com/apoorvumang/knowledge-cutoff) — measured effective knowledge late 2025 / Jan 2026 (discovery sources; the plan verifies empirically in Step 0)
- [nepflood.vercel.app](https://nepflood.vercel.app/) — presentation layout reference only (hero, sensor cards, how-it-works, findings counters, legend map); no facts or figures taken from it (inspected, non-empty, fetched this run)
