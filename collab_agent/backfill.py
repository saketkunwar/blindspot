"""Backfill: curate a fresh pull into a manifest-pinned scene, rebuild the
census over all scenes, and record what changed.

This is the learning loop's data half: same frozen rule, same frozen key,
new honest episodes. It never edits existing scenes and never touches the
frozen briefs. Run it after new pulls land in data/raw/:

  python -m collab_agent.backfill --pull data/raw/firms_iberia_ext.csv \\
      --tag firms_iberia_ext --source-url "FIRMS area API, VIIRS_NOAA20_NRT"

Outputs (defaults): data/fire_kalimantan/<tag>.json (manifest-pinned),
results/memory_episodes.sqlite3 + results/memory_census.json rebuilt from
scratch over every scene (a clean rebuild, never an append, so reruns are
idempotent), and one digest record comparing best-labelled before/after.
"""
import argparse
import csv
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collab_agent import digest as _digest  # noqa: E402
from scripts import check_manifest as _manifest  # noqa: E402

KEEP = ("acq_date", "acq_time", "latitude", "longitude", "confidence",
        "frp", "satellite", "version")


def curate(pull_path: pathlib.Path, tag: str) -> pathlib.Path:
    """Pull CSV -> scene JSON in data/fire_kalimantan/. Keeps FIRMS columns
    the parser understands; drops nothing it needs."""
    with open(pull_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "acq_date" not in rows[0]:
        raise RuntimeError(f"{pull_path} is not a FIRMS pull CSV")
    NUMERIC = ("latitude", "longitude", "frp")
    scene = []
    for r in rows:
        d = {k: r[k] for k in KEEP if k in r}
        for k in NUMERIC:  # curated scenes carry numbers, not CSV strings
            if k in d:
                d[k] = float(d[k])
        scene.append(d)
    dest = ROOT / "data" / "fire_kalimantan" / f"{tag}.json"
    if dest.exists():
        raise RuntimeError(f"scene exists, refusing to overwrite: {dest}")
    dest.write_text(json.dumps(scene, indent=1) + "\n")
    assert json.loads(dest.read_text()) == scene
    return dest


def _census_counts(census_path: pathlib.Path) -> tuple[int, int]:
    """(episodes, labelled) counted from the episode rows themselves —
    never from summary keys that may not exist."""
    c = json.loads(census_path.read_text())
    eps = c.get("episodes", [])
    unlab = "unlabelable"
    labelled = sum(1 for e in eps if e.get("label", unlab) != unlab)
    return (len(eps), labelled)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pull", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--source-url", required=True,
                    help="provenance only; must carry no key")
    ap.add_argument("--db", default="results/memory_episodes.sqlite3")
    ap.add_argument("--census-out", default="results/memory_census.json")
    ap.add_argument("--digest", default="results/morning/digest.json")
    ap.add_argument("--rules", default="demo/fire_study/rules.json")
    ap.add_argument("--memory-config", default="config/preregistered_memory.yaml")
    ap.add_argument("--no-manifest-check", action="store_true",
                    help="skip manifest record+verify (tests only: the scene "
                         "stays unregistered, so production runs must omit it)")
    args = ap.parse_args(argv)
    if "MAP_KEY" in args.source_url or "key=" in args.source_url.lower():
        print("refusing: source-url looks like it carries a key")
        return 2

    tag = "".join(ch if (ch.isalnum() or ch in "_-") else "_"
                  for ch in args.tag).lower()
    try:
        scene = curate(pathlib.Path(args.pull), tag)
    except RuntimeError as exc:
        print(f"backfill refused: {exc}")
        return 2
    if args.no_manifest_check:
        print("tests-only: scene left unregistered, manifest untouched")
    else:
        rc = _manifest.main(["--data-dir", "data", "--record",
                             f"fire_kalimantan/{tag}.json", "--kind",
                             "real", "--source-url",
                             args.source_url])
        if rc != 0:
            print("manifest record failed; scene left unregistered")
            return rc

    census_path = pathlib.Path(args.census_out)
    before = _census_counts(census_path) if census_path.exists() else (0, 0)
    cmd = [sys.executable, "scripts/backtest_episodes.py", "--all-scenes",
           "--db", args.db, "--census-out", args.census_out,
           "--rules", args.rules, "--memory-config", args.memory_config]
    if args.no_manifest_check:
        cmd.append("--no-manifest-check")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=600)
    if r.returncode != 0:
        print(f"backtest failed:\n{r.stdout[-1500:]}\n{r.stderr[-500:]}")
        return r.returncode
    after = _census_counts(census_path)
    _digest.append(ROOT / args.digest, {
        "kind": "backfill", "tag": tag,
        "episodes_before": before[0], "labelled_before": before[1],
        "episodes_after": after[0], "labelled_after": after[1],
    })
    print(f"backfill {tag}: episodes {before[0]}->{after[0]}, "
          f"labelled {before[1]}->{after[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
