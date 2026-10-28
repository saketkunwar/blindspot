# AGENTS.md

Read `BUILDER_SPEC.md` (what to build) and `docs/PLAN.md` (order + hardened gates) before writing code.
`QUESTIONS.md` holds every config decision and data finding — append, never silently guess.
Config in `config/preregistered.yaml` is frozen at git tag `prereg`. `data/` is read-only after manifesting.
Run `python scripts/validate_hardened.py --setup-only` before starting any phase; run the full gate before declaring a phase done.
