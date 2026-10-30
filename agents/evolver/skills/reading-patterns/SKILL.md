# skill: reading-patterns
# How to read the pattern table and the evolution store.

Read the memory episodes store read-only (`store/db.py: episodes_for`,
`outcomes_for`). Recompute patterns with
`engine/memory.py: patterns_from_rows` at the case's `as_of` — never trust
a stored summary; the table is a pure function of the rows. Signatures come
from `signature_for_facts` with the bins in
`config/preregistered_memory.yaml`. For traces, read `traces_for` and group
identical violation strings across distinct request hashes: one hash, one
voice, no matter how long its message. Cite row ids (episode ids, trace
rowids), never prose summaries, so every claim in the proposal is
re-checkable byte for byte.
