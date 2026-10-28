# Spec kit: read this first (for you, not for Muse)

Two folders:
- `for-builder/` goes INTO the repo. Muse can read it.
- `private/` stays OUTSIDE the repo. Muse must never see it. It holds the expected answers and the hidden tests.

## Step 1: install
```sh
unzip blindspot-spec-kit.zip && cd blindspot-spec-kit
cp -r for-builder/. /srv/verify/project/
mkdir -p /srv/verify && cp -r private /srv/verify/private && chmod -R go-rwx /srv/verify/private
pip install pyyaml pytest
```
Then save your original Gemini spec, unchanged, as `/srv/verify/private/MUSE_SPEC_FULL.md`.

## Step 2: add the data and its manifest
1. Copy your data into `/srv/verify/project/data/` (`flood_nepal/`, `fire_kalimantan/`).
2. `cd /srv/verify/project && python scripts/make_manifest.py --data-dir data`
3. Open `data/MANIFEST.json` and replace every `FILL ME` with the real source URL and licence.
4. `python scripts/check_manifest.py --data-dir data` must print `manifest ok`.

## Step 3: decide the empty config values (before the `prereg` tag)
`config/preregistered.yaml` has `null` values on purpose. The builder stops if they are empty.
Decide each one from a rule, never by looking at the demo cells.
| Value | A sensible way to decide |
|---|---|
| `ingest_deg` | 0 unless the files are rounded. Write the reason down. |
| `min_detections` | A rule from FIRMS (for example a cluster size that filters noise). Do not tune it on the demo cells. |
| `footprint_buffer_m` | About half a VIIRS pixel (roughly 190 m). |
| `v_max_m_per_hr` | Take a cited speed for flood or debris waves in this region. |
| `neck_rule` | One written rule, for example the narrowest cross-section between two named points. |
| `evasion_ha_per_cell` | See problem 5 below. |
Then `git add -A && git commit && git tag prereg`.

## Step 4: add to `judge.sh`
```bash
export BLINDSPOT_ROOT=/srv/verify/project
python scripts/check_manifest.py --data-dir data
python /srv/verify/private/scripts/no_spec_literals.py
# ... the existing gates ...
pytest /srv/verify/private/hidden -q --tb=no -p no:cacheprovider    # turn this on once the pipelines exist (Phase 3)
```
Failures print only claim ids, never expected values. Keep it that way when you feed `judge.log` back to Muse.
Soft claims are written to `/srv/verify/private/results/soft_claims.json`.

## What I tested, and what I did not
Tested: both manifest scripts (pass, tampered file, unlisted file, missing source), the literal scan
(it catches cheats and ignores look-alikes like `12150`), the data-shifting helpers and the claim checks on fake data,
that `claims.yaml` loads, and that all 21 hidden tests are collected.
Not tested: anything against your real data or real pipelines (they do not exist yet).
The FIRMS file layout is a guess. The helpers handle three common layouts; if yours differs,
edit `_records` in `private/hidden/helpers.py` and re-run `python selftest.py`.

## Problems I found in the Gemini spec (decide these before you build)
1. **BEFORE vs MEETS.** The spec says Mobilization `[Sep 16, Sep 17)` is BEFORE Clearing `[Sep 17, Sep 21)`. The end of one equals the start of the other, so by endpoints it is MEETS. `claims.yaml` expects `m`. Fix the pitch wording.
2. **The 14.6 m bridge band.** Layer 4 makes anything under 50 m `IMMEDIATE_ENVELOPE`, but the demo script calls 14.6 m "NEAR". `claims.yaml` follows Layer 4.
3. **"All 9 tiles".** True for the flood seen from the bridge, not for the bridge seen from the flood. The builder spec defines the direction.
4. **Counts to RCC-8.** The spec never says how detection counts become DC, NTPP or PO. I wrote a footprint rule into `BUILDER_SPEC.md` (task T-3.3). Read it. The RCC-8 sequences are soft claims, so a different rule will not fail the build.
5. **The 150 ha test cannot work as written.** One VIIRS detection is about 14 ha, so a cell with 25 detections is already about 350 ha. "Each cell stays under the threshold while the patch exceeds 150 ha" will not hold with these counts. Redefine it (per day, per concession block, or a different threshold) or drop the evasion hypothesis.
6. **Barrier-lake data is missing.** Act 3 needs `flood_nepal/barrier_lake.geojson` and `flood_nepal/sar_anomaly_union.geojson`. Until they exist the two Act 3 claims are skipped and the pipeline reports `missing_input`.
7. **Scoreboard numbers** ("Paper section 13") are not produced by this repo. They must come from your judge's `evidence.json`.
