# collab_agent — the morning-brief agent (fire)

Wakes on your machine, pulls the last five days of FIRMS detections for the
study box, studies them with the frozen September rules, and writes a 2–3
line human snippet — or one quiet line when nothing fires. No model writes
digest prose; snippets are fixed templates over ledger values, and every
number in a snippet must already exist in its ledger block (checked before
anything is written).

## What it never does

- Never touches the frozen briefs (gate-verified byte-identical).
- Never puts the pull in `data/` or the frozen study.
- Never invents a trigger, a threshold, or a reading: triggers live in
  `config.yaml`, preregistered with reasons in `QUESTIONS.md`
  ("Morning-brief triggers"). Changing one is a versioned amendment.
- Never proposes rule changes by itself: the evolver's propose-test-wait
  path still needs your written approval.
- Never phones home: the only network call is the FIRMS pull itself.

## Run it once (no key, no network)

```bash
python -m collab_agent.morning --fixture oct30
```

Replays the committed October 30 pull into `results/morning/` and writes
`api/demo2_data/morning.json` (committed deliberately, like the live CSV).

## Run it for real (needs a key)

```bash
export FIRMS_MAP_KEY='<key>'   # or NASA_FIRMS_MAP_KEY
python -m collab_agent.morning --live
```

Without a key it logs `skipped` and exits 0 — silence is reported, never
faked. Keys travel in the environment only.

## Every morning (cron on your machine)

```cron
15 6 * * * cd /path/to/blindspot && FIRMS_MAP_KEY='<key>' python -m collab_agent.morning --live >> results/morning/cron.log 2>&1
```

P4 stays parked: this is your-machine scheduling with human-held rule
changes, not a hosted autonomous service. Read the digest with
`python scripts/status.py` (morning-brief section lands with the status
work) or open the latest snippet in `api/demo2_data/morning.json`.
