# AGENTS.md

Read `BUILDER_SPEC.md` (what to build) and `docs/PLAN.md` (order + hardened gates) before writing code.
`QUESTIONS.md` holds every config decision and data finding — append, never silently guess.
Config in `config/preregistered.yaml` is frozen at git tag `prereg`. `data/` is read-only after manifesting.
Run `python scripts/validate_hardened.py --setup-only` before starting any phase; run the full gate before declaring a phase done.
Write every user-visible message in full human sentences, simple English with technical depth for non-experts: explain in flowing prose with a beginning, middle, and end — one idea leading into the next — never as discrete cobbled fragments, shorthand, or machine-shaped lists. Write like a poet and a scientific researcher combined: concrete images and plain words first, numbers woven into the story, never bare. No slop dashboard prose.
