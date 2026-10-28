# Plans for Everything — BlindSpot Master Roadmap

One file, every plan. The scientific core is proven (Nepal demo: rank-1
GT match, G1–G12 ALL PASS). What follows sequences the remaining work so
nothing is built out of order: **P0 finishes the science, P1 rebuilds the
delivery fabric, P2–P4 harden for real use, P5 is the discipline that
keeps P0–P4 honest.** Each plan ends with its own gate; a plan is done
only when its gate passes.

Cross-reference: [FLEX_NS_PLAN.md](./FLEX_NS_PLAN.md) (P0 detail),
[PHASES.md](./PHASES.md) (what exists), [PROGRESS_ERROR.md](../PROGRESS_ERROR.md)
(hardened lessons).

## P0 — Flexible neurosymbolic core (science; NEXT)

Make the study pipeline domain-generic so Demo 2 (fire) runs with zero
`engine/`/`agents/` edits. Steps, gates, and risks are fully specified in
[FLEX_NS_PLAN.md](./FLEX_NS_PLAN.md) (Steps 0–7, gates G13/G3b/G14/G15).

- **Gate:** flood brief byte-identical post-refactor; G1–G15 ALL PASS;
  git log for Demo 2 shows no `engine/`/`agents/` paths.
- **Status:** ready to execute on `go`.

## P1 — Delivery fabric rebuild (after P0)

Replace the demo shell around the proven core — do not stretch it.

0. **Docs consolidation (first, half a day).** Index + merge + retire:
   one entry point (`README` → `USAGE_DEMO.md` → study insights), merge
   the sketch sections that [FLEX_NS_PLAN.md](./FLEX_NS_PLAN.md) already
   reviewed into it, retire anything superseded with a one-line pointer
   left behind. Nothing rewritten from scratch.
   **Gate:** a new reader reaches replay instructions in two clicks from
   the README; no two docs own the same section.
1. **API shape:** versioned read API (`/v1/studies/{id}/brief`, `/geo`,
   `/gt`) over frozen study artifacts; live/cached mode labels preserved;
   OpenAPI schema checked into repo; contract tests pinned.
2. **Persistence:** typed store (SQLite first, Postgres-ready schema) for
   studies, runs, cassettes, and audit trails — every artifact content-
   hashed (SHA-256) as in `data/MANIFEST.json`; writes are append-only,
   runs are immutable.
3. **Auth & tenancy:** single-operator token first; per-study read tokens;
   no multi-user features until P4 evidence demands them.
4. **Presentation:** server-rendered study pages from the store (hero →
   evidence → how-it-works → ranking → findings → legend map), print CSS
   for briefs; the current client page is the visual reference, not the base.
5. **Rebuild entry point:** one taskfile/Makefile target — clean checkout
   → install → manifest → gates → seed → API → web → judge, all green.

- **Gate:** clean-checkout rebuild green end-to-end (G16); API contract
  tests pass; no seeded/filler data anywhere in the served path.

## P2 — Data persistence & provenance

Make every byte the pipeline touches traceable and durable.

1. Manifest discipline extended to studies: curated inputs, cards,
   prompts, drafts, briefs, GT checks — all hashed and listed.
2. Backup/restore drill: wipe `results/` + store, rebuild from manifest +
   cassettes, byte-identical briefs (extends G14 to the full stack).
3. Ingest watch: new raw files under `data/raw/` fail CI until curated
   with source + licence (G1 stays fail-closed; no silent growth).

- **Gate:** restore drill green; G1 green with zero manual manifest edits
  for one full study cycle.

## P3 — Execution & operations

Run studies like an operator, not a demo.

1. Run registry: every study run logged (inputs hash, rules hash, model
   id, cassette hashes, operator, timestamp) — `meta_usage.json` becomes
   a table, not a file.
2. Key management: API keys via env/secret store only; cassette-record
   runbook (record → replay → freeze) documented in `USAGE_DEMO.md`.
3. Health endpoints + structured logs on the API; one-command status
   (`studies`, `runs`, `gates` summary).
4. Scheduled verification: nightly `validate_hardened.py` + judge in CI;
   failures open an issue, never auto-fix.

- **Gate:** a study executed start-to-finish from the runbook by a fresh
  operator (or agent) with no improvisation; CI green for 7 days.

## P4 — Scale & product-fit (FROZEN until evidence)

Explicitly parked until real users with real data volumes appear:
multi-study dashboards, fleet/map workloads, background/offline sync,
migration tooling, PWA, multi-tenancy, public hosting. Unfreezing
requires: two studies operated in production (P3), a named user group,
and a written problem statement tied to observed usage — not anticipation.

- **Gate to unfreeze:** P3 complete + evidence memo reviewed.

## P5 — Discipline (always on)

1. Per-phase `PROGRESS_ERROR.md` entries with `[plain]`/`[hardened]` tags
   and top findings — no phase closes without one.
2. Rules/config changes need a new tag + full re-run (`prereg` precedent);
   frozen studies are never edited in place.
3. GT discipline: ground truth read only after freeze, reported as-is
   (match or mismatch), no re-tuning afterward.
4. Docs debt cap: any new `.md` must replace or extend an existing one;
   the next reader gets one entry point (`USAGE_DEMO.md` +
   [insights_flood.md](../demo/nepal_cascade/insights_flood.md)).

## Order & dependencies

P0 → P1 → P2 → P3 → (P4 only on evidence). P5 runs throughout.
P1 may not start until P0's Demo-2 acceptance proves the study shape is
stable — rebuilding the fabric around a still-moving core is how the
demo shell became fragile.
