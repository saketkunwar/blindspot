# skill: writing-proposals
# How to write a proposal the structural check will accept.

A proposal has: `track` (A for these files, B for rules), `issue` (one
plain-sentenced paragraph: what recurs, where, with what effect),
`recurrence` (count of independent episodes or runs), `change` (exactly
one: for Track B today, `{"weight": {fact_id, old_weight, new_weight}}`
where old_weight must equal the frozen file), `cited_episodes` and
`cited_traces` (ids you read), `rejected` (what you saw and set aside),
and for Track B the `base_rules_sha` of the frozen file it amends. Write
status `candidate` when the change is not yet complete — a candidate can
never be approved; a human completes it via review submit. Before writing,
read the verdicts: a refused change stays refused without new evidence.
