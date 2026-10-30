#!/usr/bin/env python3
"""One deterministic hill-climbing step (M3a): analyze, then stop.

Reads the traces store and the memory episodes store, looks for recurring
failures, and files at most `max_proposals_per_run` candidate proposals
(issue + evidence, never a complete change — candidates cannot be
approved). Then it stops and waits for a person. It never applies anything,
never calls a model, and never reads a row past `--as-of`: episodes whose
outcome window was still open are excluded from mining, evidence, and the
report alike, so rebuilding the inputs without them reproduces this report
byte for byte (G24).

Today's honest output on real data is usually "nothing meets the bar" —
with two labelled episodes no pattern qualifies, and clean setup replays
leave no recurring violation. That no-op is exit 0: a correct negative.

Usage:
  python scripts/hill_climb.py --traces-db <traces.sqlite3>
      --evolver-db <evolver.sqlite3> [--memory-db <episodes.sqlite3>]
      [--memory-config config/preregistered_memory.yaml] [--as-of ISO-day]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import evolution as _evo  # noqa: E402
from engine import memory as _memory  # noqa: E402
from store import db as _db  # noqa: E402
import yaml as _yaml


def _load_traces(db_path: str) -> list:
    p = pathlib.Path(db_path)
    if not p.is_file():
        return []
    con = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    try:
        return _db.traces_for(con)
    finally:
        con.close()


def _mine_traces(traces: list, min_recurrence: int) -> list:
    """Group identical violations across distinct runs (one request hash,
    one voice). Returns candidate dicts, most-recurring first."""
    by_violation: dict = {}
    for t in traces:
        for v in json.loads(t["violations"] or "[]"):
            by_violation.setdefault(v, {}).setdefault(
                t["request_hash"], []).append(t["rowid"])
    candidates = []
    for violation, per_hash in sorted(by_violation.items()):
        hashes = sorted(per_hash)
        if len(hashes) < min_recurrence:
            continue
        rowids = sorted(r for h in hashes for r in per_hash[h])
        candidates.append({
            "track": "A",
            "issue": (f"Setup rounds fail {len(hashes)} independent runs "
                      f"with: {violation}"),
            "recurrence": len(hashes),
            "cited_traces": rowids,
            "cited_episodes": [],
            "rejected": [],
        })
    return candidates


def _mine_patterns(memory_db: str | None, mem: dict, as_of: str,
                   min_recurrence: int) -> list:
    """Patterns with a real history whose frozen top is never backed by any
    observed outcome: the frozen rules mishandle exactly this signature."""
    if not memory_db:
        return []
    try:
        episodes, outcomes = _memory.read_episodes_outcomes(memory_db)
    except (FileNotFoundError, OSError):
        return []
    patterns = _memory.patterns_from_rows(
        episodes, outcomes, mem["signature"]["count_bin_edges"],
        mem["memory"]["outcome_supports"], as_of,
        mem.get("rule_id", "memory-v1"))
    supports = mem["memory"]["outcome_supports"]
    backed_by = {m: lab for lab, ms in supports.items() for m in ms}
    candidates = []
    for sig in sorted(patterns):
        p = patterns[sig]
        if p["labeled"] < max(min_recurrence,
                              mem["memory"]["min_episodes_to_speak"]):
            continue
        label_of = {}
        for o in outcomes:
            if o.get("window_end") and o["window_end"] <= as_of and \
                    o.get("label") not in ("unlabelable",):
                label_of[o["episode_id"]] = o["label"]
        tops = {}
        for ep in episodes:
            lab = label_of.get(ep["episode_id"])
            if lab is None:
                continue
            if _memory.signature_for_facts(
                    ep.get("facts") or {},
                    mem["signature"]["count_bin_edges"])["id"] != sig:
                continue
            tops[ep["top_mechanism"]] = lab
        if tops and all(backed_by.get(t) != lab for t, lab in tops.items()):
            ep_ids = sorted(
                ep["episode_id"] for ep in episodes
                if _memory.signature_for_facts(
                    ep.get("facts") or {},
                    mem["signature"]["count_bin_edges"])["id"] == sig
                and ep["episode_id"] in label_of)
            candidates.append({
                "track": "B",
                "issue": (f"Pattern {sig[:12]}: {p['labeled']} labelled "
                          f"episodes and the frozen top was backed by none "
                          f"of their outcomes"),
                "recurrence": p["labeled"],
                "cited_traces": [],
                "cited_episodes": ep_ids,
                "rejected": [],
            })
    return candidates


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--traces-db", required=True)
    ap.add_argument("--evolver-db", required=True)
    ap.add_argument("--memory-db", default=None)
    ap.add_argument("--memory-config",
                    default=str(ROOT / "config/preregistered_memory.yaml"))
    ap.add_argument("--as-of", default=None,
                    help="ISO day; defaults to the latest closed outcome window")
    a = ap.parse_args(argv)
    mem = _yaml.safe_load(pathlib.Path(a.memory_config).read_text())
    evo = mem["evolver"]
    as_of = a.as_of
    if as_of is None and a.memory_db:
        try:
            _, outcomes = _memory.read_episodes_outcomes(a.memory_db)
        except (FileNotFoundError, OSError):
            outcomes = []
        ends = sorted(o.get("window_end") or "" for o in outcomes
                      if o.get("label") not in ("unlabelable",))
        as_of = ends[-1] if ends else None
    if as_of is not None:
        _memory.check_as_of(as_of)

    traces = _load_traces(a.traces_db)
    found = _mine_traces(traces, int(evo["min_recurrence"]))
    if as_of is not None:
        found += _mine_patterns(a.memory_db, mem, as_of,
                                int(evo["min_recurrence"]))
    kept, dropped = _evo.cap_proposals(
        found, int(evo["max_proposals_per_run"]))

    con = sqlite3.connect(a.evolver_db)
    try:
        con.executescript(_db.SCHEMA)
        for c in kept:
            _db.add_proposal(con, c["track"], "candidate", c["issue"],
                             c["recurrence"], {}, c["cited_episodes"],
                             c["cited_traces"], c["rejected"])
        con.commit()
    finally:
        con.close()
    report = {"as_of": as_of,
              "traces_read": len(traces),
              "candidates_found": len(found),
              "candidates_filed": len(kept),
              "dropped_over_cap": dropped,
              "filed": [{"track": c["track"], "recurrence": c["recurrence"],
                         "cited_traces": c["cited_traces"],
                         "cited_episodes": c["cited_episodes"]}
                        for c in kept]}
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
