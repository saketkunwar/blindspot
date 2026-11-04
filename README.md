# BlindSpot

When cloud and smoke blind the satellites, most systems wait. BlindSpot
reasons across the gap instead — in space and time together — and every
conclusion carries the relations it came from.

It was born when cloud cover blinded satellites during the Nepal floods.
The valley had been hit, the sky stayed shut for days, and the next clear
image arrived too late to triage anyone. BlindSpot is the answer to that
week: a system that reads what happened inside the blind hours from the
geometry around them, writes its verdict down before the truth opens, and
then lets the sealed ground truth grade it.

## What it proved

Two frozen studies, both fixed before their ground truth opened:

- **Nepal flood cascade.** From pre-cutoff geometry alone, the ledger
  scored impoundment-then-burst first at 0.9426 and triaged 171 bridges
  inside a 172.8-kilometre band. The sealed envelope later held 754 newly
  destroyed features in exactly the burst path.
- **Kalimantan peat fire.** From five September days, the system scored
  suppression-then-restart at 0.8425 — a signal so pervasive the ranking
  came back identical with half the map deleted. Three Meta Muse models
  (spark 1.2, 1.3, wonder 1.0) independently pointed at the same lead
  facts with zero citation errors. In late October the fire restarted on
  schedule, and the morning watch caught the October 30 spike live: 150
  detections against a trailing median of 18.5, memory honestly silent at
  four of five labelled.

A third piece watches daily. The collaborative morning agent pulls fresh
satellite data, studies it with the frozen rules, asks sixty past fire
episodes across six continents, and writes two human lines — including what
would prove it wrong. It runs on manners, not powers: it never applies a
rule change itself. A deterministic miner files recurring failures as
candidates, people author any change, and a replay judge tests it before
human sign-off.

For the full story — the algebra, the procedures step by step, the memory
design, the verification log — read [blindspot.pdf](blindspot.pdf), the
paper at the root of this repo.

## Run the showcase (5 minutes, no key needed)

Two terminals, from the repo root:

```sh
# Terminal 1 — the API (always from the repo root, never from web/)
uvicorn api.server:app --port 8000

# Terminal 2 — the console (first time only: npm install inside web/)
cd web && npm run dev
```

Then open `http://localhost:3000/demos`. The root URL redirects there.
Start with the seven stories — each pairs what the engine saw inside a
sensing gap with the proof it could not have cheated:

| Story | What it shows |
|---|---|
| The blindfold reveal | The valley verdict spoken without the aftermath, then 754 sealed features matching it |
| The triage map | 195 assets sorted into the maybe-band while the model cried safe and the kernel overruled it |
| The maths that cannot teleport | The gates that bit before the freeze, including the 313,269-to-one bug that became 1.06 |
| The zombie fire | A disappearance read as evidence at 0.8425, the future sealed until the freeze |
| Cut the map in half | The entire eastern half deleted live; every probability returns to zero drift |
| The awakening | Four was silence and five was a voice, across three continents |
| The watchman | One October morning minute by minute, and the mind it honestly lacks yet |

Below the stories, four deep dives carry the frozen verdicts, the live
morning-agent button, the memory desk with its recall tier, and the
cross-region study. Every map opens on satellite imagery with clickable
features and a Before/After reveal of the ground truth the brief never saw.

## How it stays honest

- **Frozen first.** Configuration locks under a version tag and inputs are
  hash-pinned before anything runs. Ground truth opens only after the
  freeze and is never tuned against.
- **Default-deny gate.** Every machine-written number must already exist
  in the evidence ledger, or the brief is blocked. Memory claims pass
  through the same gate.
- **Byte-for-byte replay.** The frozen briefs reproduce exactly from
  recorded model conversations — no key, no network. Deleting everything
  recorded after a case's cutoff must change nothing; that check runs as a
  gate, not a hope.
- **Silence is a result.** Flood memory is empty (two dated days against
  8,368 dateless features) and says so. October 30 memory stood at four
  of five and stayed silent. A flat measurement is reported, never rounded
  up.

Verify it yourself:

```sh
python scripts/validate_hardened.py   # hardened gates G1–G25, all pass
bash scripts/judge.sh                 # 166 checks green, offline replay
python -m pytest tests/properties/test_serving.py -q   # serving, 8 passed
npm run build --prefix web            # console, 19 routes
```

## Repo map

- `blindspot.pdf` — the paper. Start here for depth.
- `api/server.py` — read-only API; the only state it keeps is committed demo snapshots.
- `web/` — the console and all demo pages.
- `engine/`, `agents/`, `collab_agent/` — the qualitative kernel, the role prompts, the morning watch.
- `config/preregistered.yaml` — every magic number, decided by rule before results, frozen at tag `prereg`.
- `data/` — read-only after manifesting. `papers/draft1/` — paper source and figures.
- `QUESTIONS.md` — every config decision and data finding, appended not guessed.
- `docs/PLAN.md`, `docs/PHASES.md` — build order and build record.

## Honest limits (stated, not buried)

- Satellite imagery is one current vintage: context for the eye, never evidence.
- The flood study's spatial holdout is still openly pending; the temporal check passed.
- Free-tier hosting sleeps: the first judge click on a cold API takes about a minute.
- API keys travel by environment only, never in files or logs. Anything once pasted in chat is rotated.
