#!/usr/bin/env python3
"""Seed the study store from frozen repo artifacts (P1 persistence).

Rebuild semantics: the store is derived state, so seeding removes any
existing database file and rebuilds it from the committed files. Every
row pins a SHA-256; nothing is invented. Run: `python scripts/seed_store.py
[--root .] [--out results/store.sqlite3]`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store import db as store  # noqa: E402

STUDIES = (
    # (store id, demo dir, representative inputs file for the run record)
    ("nepal-cascade", pathlib.Path("demo") / "nepal_cascade", "pre_t1_features.geojson"),
    ("kalimantan-fire", pathlib.Path("demo") / "fire_study", "detections.geojson"),
)


def _frozen_at(demo: pathlib.Path) -> str:
    line = next((ln for ln in (demo / "BASELINE.sha256").read_text()
                 .splitlines() if ln.startswith("# Frozen ")), "")
    m = re.match(r"# Frozen (\d{4}-\d{2}-\d{2}T[\d:.+-]+Z?)", line)
    if not m:
        raise SystemExit(f"{demo}/BASELINE.sha256 carries no Frozen timestamp")
    return m.group(1)


def seed(root: pathlib.Path, out: pathlib.Path) -> dict:
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    con = store.connect(out)
    studies = {}
    try:
        for study_id, rel, inputs_file in STUDIES:
            demo = root / rel
            brief = json.loads((demo / "output" / "brief.json").read_text())
            domain = json.loads((demo / "domain.json").read_text())
            meta = {"as_of_label": brief.get("as_of_label"),
                    "baseline": store.sha256_file(demo / "BASELINE.sha256")}
            store.add_study(con, study_id, domain.get("domain_id", ""),
                            _frozen_at(demo), meta)
            hashes = {}
            Kinds = [("brief", demo / "output" / "brief.json"),
                     ("gt", demo / "output" / "gt_check.json"),
                     ("rules", demo / "rules.json"),
                     ("inputs-audit", demo / "inputs" / "input_audit.json"),
                     ("card", demo / "output" / "card.json")]
            for kind, full in Kinds:
                if full.is_file():
                    hashes[kind] = store.add_artifact(
                        con, study_id, kind, full.relative_to(root))
            cassette = str((brief.get("model_round") or {}).get("request_hash", ""))
            if cassette:
                cassette_path = (root / "data" / "model_cassettes" / f"{cassette}.json")
                if cassette_path.is_file():
                    hashes["cassette"] = store.add_artifact(
                        con, study_id, "cassette", cassette_path.relative_to(root))
            rules_hash = store.sha256_file(demo / "rules.json")
            inputs_hash = store.sha256_file(demo / "inputs" / inputs_file)
            model_id = str((brief.get("model_round") or {}).get("model", ""))
            brief_hash = store.sha256_file(demo / "output" / "brief.json")
            run_id = store.add_run(con, study_id, inputs_hash, rules_hash, model_id,
                                   [cassette] if cassette else [], brief_hash,
                                   operator=os.environ.get("USER", "seed"))
            store.audit(con, "seed", "seed-study",
                        {"study": study_id, "run": run_id,
                         "artifacts": sorted(hashes)})
            studies[study_id] = {"run": run_id, "artifacts": hashes}
        con.commit()
    finally:
        con.close()
    return {"studies": studies,
            "artifacts": {sid: s["artifacts"] for sid, s in studies.items()},
            "db": str(out)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default="results/store.sqlite3")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    out = pathlib.Path(a.out)
    if not out.is_absolute():
        out = root / out
    summary = seed(root, out)
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
