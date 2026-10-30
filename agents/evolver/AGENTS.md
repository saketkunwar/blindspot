# Evolver agents — always-on rules (Track A, version 1)

These rules govern the proposing agents. They change only by a new version
of this file, reviewed by a person — never edited in place. They cannot
change any scientific result: Track A covers these instruction files only.
Rule changes (Track B) need a human verdict plus a passing held-out replay.

1. Never cite an episode, trace, replay, or verdict that does not exist.
   Every id in a proposal must come from a row you actually read.
2. Exactly one change per proposal. A second idea is a second proposal.
3. Never read anything recorded after the case's `as_of`. An outcome whose
   window was still open is knowledge the case could not have had yet.
4. Recurrence is counted over independent episodes (cutoffs at least
   `independence_gap_days` apart in `config/preregistered_memory.yaml`).
   Neighboring slides share most of their data and count once.
5. Track B opens weight-only. Proposing any other change kind is refused
   by the structural check — do not try to wordsmith around it.
6. Record what you noticed and set aside in `rejected`, so the next run
   can pick it up instead of rediscovering it.
7. Earlier human rejections outrank new proposals: check the verdicts
   first, and do not re-propose a refused change without new evidence.
8. You may write proposal rows (status `candidate` only — a candidate
   names the issue and evidence, never a complete change). You may never
   write verdicts, apply changes, edit frozen files, or tag versions.
