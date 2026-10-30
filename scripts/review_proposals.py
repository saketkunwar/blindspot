#!/usr/bin/env python3
"""Human review for evolution proposals (M3b): submit, replay, decide.

The machine proposes and replays; only a person decides. Every refusal
exits 2 with the reason printed — a proposal that does not clear its bar
fails loudly instead of sliding through:

- submit: validates a human-authored proposal and files it as pending.
- replay: runs the Skeptic's deterministic held-out replay and appends the
  result (re-running appends; it never overwrites).
- approve: needs a written --reason, a pending proposal with no verdict
  yet, and a latest replay that beats the frozen rules by the preregistered
  margin on held-out episodes without moving the frozen top — or an
  explicit --override reason, recorded just as loudly. Writes the verdict,
  then the modified rules to --out (a live file under results/, never into
  the frozen demo directory). Tagging and freezing stay human hands.
- reject: records a refusal with its reason, so the next run stops
  re-proposing it.
- list: every proposal with its status, latest replay edge, and verdict.

Usage:
  python scripts/review_proposals.py --db <evolver.sqlite3> submit --file proposal.json --memory-db M --traces-db T
  python scripts/review_proposals.py --db <evolver.sqlite3> replay --id N --memory-db M [--as-of ISO-day]
  python scripts/review_proposals.py --db <evolver.sqlite3> approve --id N --reason "..." [--override "..."]
  python scripts/review_proposals.py --db <evolver.sqlite3> reject --id N --reason "..."
"""
from __future__ import annotations

import argparse
import hashlib
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


def _refuse(msg: str) -> int:
    print(f"refused: {msg}")
    return 2


def _mem_cfg(path: str) -> dict:
    return _yaml.safe_load(pathlib.Path(path).read_text())


def _base_shas() -> dict:
    out = {}
    for study in ("nepal_cascade", "fire_study"):
        rp = ROOT / "demo" / study / "rules.json"
        out[study] = hashlib.sha256(rp.read_bytes()).hexdigest()
    return out


def _study_for_sha(sha: str) -> str | None:
    for study, value in _base_shas().items():
        if value == sha:
            return study
    return None


def _known_ids(memory_db: str | None, traces_db: str | None) -> tuple:
    eps, traces = set(), set()
    if memory_db:
        try:
            episodes, _ = _memory.read_episodes_outcomes(memory_db)
            eps = {e["episode_id"] for e in episodes}
        except (FileNotFoundError, OSError):
            pass
    if traces_db:
        p = pathlib.Path(traces_db)
        if p.is_file():
            con = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
            try:
                traces = {t["rowid"] for t in _db.traces_for(con)}
            finally:
                con.close()
    return eps, traces


def _roles_for_episode(ep: dict, mem: dict):
    """Rebuild one episode's ledger roles from the pinned scene file the
    episode cites (matched by sha, read-only). No stored summary is trusted:
    the slice, the grid, and the extent are recomputed pre-cutoff only."""
    from scripts import backtest_episodes as _be
    from pipelines.loader import parse_firms_detections
    digest = ep["scene_sha256"]
    scene = next((p for p in (ROOT / "data/fire_kalimantan").glob("*.json")
                  if hashlib.sha256(p.read_bytes()).hexdigest() == digest),
                 None)
    if scene is None:
        raise KeyError(f"no pinned scene matches {ep['scene']}")
    _be._verify_scene(scene, ROOT / "data")
    obj = json.loads(scene.read_text())
    dets = [(d, lo, la) for d, lo, la in parse_firms_detections(obj)
            if d <= ep["cutoff"]]
    if not dets:
        raise ValueError(f"episode {ep['episode_id']}: empty pre-cutoff slice")
    cm = mem.get("curation_mirror") or {}
    roles, _ = _be._build_roles(
        dets, cm.get("grid_cell_deg", 0.5),
        cm.get("noise_floor_detections", 3))
    return roles


def _frozen_top_with_rules(study: str, rules: dict) -> str:
    """The frozen study's top story recomputed under the given rules."""
    from engine.ledger import (compute_ledger, compute_ledger_from_spec,
                               score_mechanisms)
    demo = ROOT / "demo" / study
    domain = json.loads((demo / "domain.json").read_text())
    inputs = demo / "inputs"
    if "ledger_spec" in rules:
        from engine import facts as _facts
        roles = _facts.load_inputs_by_role(domain, inputs)
        ledger = compute_ledger_from_spec(rules, roles)
    else:
        feats = json.loads((inputs / "pre_t1_features.geojson").read_text())["features"]
        waterways = json.loads((inputs / "waterways.geojson").read_text())
        target = json.loads((inputs / "target_reach.geojson").read_text())["features"]
        extent = json.loads((inputs / "extent.json").read_text())
        geom = {"type": "Polygon", "coordinates": [[
            [extent["bbox"][0], extent["bbox"][1]], [extent["bbox"][2], extent["bbox"][1]],
            [extent["bbox"][2], extent["bbox"][3]], [extent["bbox"][0], extent["bbox"][3]],
            [extent["bbox"][0], extent["bbox"][1]]]]}
        ledger = compute_ledger(feats, waterways, target, geom, rules,
                                domain=domain)
    return score_mechanisms(rules, ledger)[0]["id"]


def cmd_submit(a, con) -> int:
    mem = _mem_cfg(a.memory_config)
    prop = json.loads(pathlib.Path(a.file).read_text())
    eps, traces = _known_ids(a.memory_db, a.traces_db)
    violations = _evo.validate_proposal(prop, eps, traces,
                                        mem["evolver"], _base_shas())
    if violations:
        return _refuse("proposal fails structural check: " + "; ".join(violations))
    pid = _db.add_proposal(con, prop["track"], "pending", prop["issue"],
                           int(prop["recurrence"]), prop["change"],
                           prop.get("cited_episodes", []),
                           prop.get("cited_traces", []),
                           prop.get("rejected", []),
                           prop.get("base_rules_sha", ""))
    con.commit()
    print(f"filed pending proposal {pid}")
    return 0


def cmd_replay(a, con) -> int:
    mem = _mem_cfg(a.memory_config)
    evo = mem["evolver"]
    props = {p["rowid"]: p for p in _db.proposals_for(con)}
    prop = props.get(a.id)
    if prop is None:
        return _refuse(f"no proposal {a.id}")
    if prop["status"] != "pending":
        return _refuse(f"proposal {a.id} is {prop['status']}, not pending")
    change = json.loads(prop["change_json"])
    study = _study_for_sha(prop.get("base_rules_sha") or "")
    if study is None:
        return _refuse("base rules match no frozen study")
    base_rules = json.loads((ROOT / "demo" / study / "rules.json").read_text())
    episodes, outcomes = _memory.read_episodes_outcomes(a.memory_db)
    as_of = a.as_of
    if as_of is None:
        ends = sorted(o.get("window_end") or "" for o in outcomes
                      if o.get("label") not in ("unlabelable",))
        as_of = ends[-1] if ends else None
    if as_of is None:
        return _refuse("no closed outcome windows to replay against")
    _memory.check_as_of(as_of)
    cutoffs = sorted({e["cutoff"] for e in episodes})
    spans = _evo.time_slices(cutoffs, float(evo["split_propose_frac"]),
                             float(evo["split_validate_frac"]))
    cited_days = sorted({e.split("@")[-1] for e in
                         json.loads(prop["cited_episodes"])})
    if cited_days and cited_days[0] >= min(spans["validate"] or ["~"]):
        result = {"contaminated": True,
                  "note": "cited evidence reaches the validation span; "
                          "the comparison would grade its own homework"}
        _db.add_replay(con, a.id, result)
        con.commit()
        print(json.dumps(result, indent=1, sort_keys=True))
        return _refuse("cited evidence overlaps the held-out span")
    label_of = {o["episode_id"]: o["label"] for o in outcomes
                if o.get("window_end") and o["window_end"] <= as_of
                and o.get("label") not in ("unlabelable",)}
    held = [e for e in episodes if e["cutoff"] in spans["validate"]
            and e["episode_id"] in label_of]
    result = _evo.skeptic_replay(
        base_rules, change, held, label_of,
        mem["memory"]["outcome_supports"],
        lambda ep: _roles_for_episode(ep, mem))
    try:
        frozen_now = _frozen_top_with_rules(
            study, _evo.apply_weight_change(base_rules, change))
    except (KeyError, ValueError) as e:
        return _refuse(f"cannot apply change: {e}")
    frozen_was = json.loads(
        (ROOT / "demo" / study / "output/brief.json").read_text()
    )["mechanisms"][0]["id"]
    result["frozen_top_kept"] = frozen_now == frozen_was
    result["as_of"] = as_of
    result["contaminated"] = False
    _db.add_replay(con, a.id, result)
    con.commit()
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


def cmd_approve(a, con) -> int:
    mem = _mem_cfg(a.memory_config)
    evo = mem["evolver"]
    props = {p["rowid"]: p for p in _db.proposals_for(con)}
    prop = props.get(a.id)
    if prop is None:
        return _refuse(f"no proposal {a.id}")
    if prop["status"] != "pending":
        return _refuse(f"proposal {a.id} is {prop['status']}; "
                       "only pending proposals are decidable")
    if _db.verdicts_for(con, a.id):
        return _refuse(f"proposal {a.id} already has a verdict")
    if not (a.reason or "").strip():
        return _refuse("approval needs a written --reason")
    replays = _db.replays_for(con, a.id)
    latest = replays[-1]["result"] if replays else None
    bar = (latest and not latest.get("contaminated")
           and latest.get("episodes", 0) >= 1
           and latest.get("edge", -1) >= float(evo["min_win_margin"])
           and latest.get("frozen_top_kept"))
    override = (a.override or "").strip()
    if not bar and not override:
        return _refuse("latest replay clears nothing "
                       f"({(latest or {})}); refusing without --override")
    change = json.loads(prop["change_json"])
    study = _study_for_sha(prop.get("base_rules_sha") or "")
    if study is None:
        return _refuse("base rules match no frozen study")
    base_rules = json.loads((ROOT / "demo" / study / "rules.json").read_text())
    try:
        new_rules = _evo.apply_weight_change(base_rules, change)
    except (KeyError, ValueError) as e:
        return _refuse(f"cannot apply change: {e}")
    out = pathlib.Path(a.out) if a.out else (
        ROOT / "results" / f"proposed_rules_{a.id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(new_rules, indent=1, sort_keys=True) + "\n")
    reason = a.reason.strip()
    if override:
        reason += f" [OVERRIDE: {override}]"
    _db.add_verdict(con, a.id, "approve", reason, a.operator or "")
    con.commit()
    print(f"approved proposal {a.id}; verdict recorded; rules written to {out}")
    print("human next: review the diff, run agents.setup_study + the full "
          "gate on the new rules, then freeze under a new tag (see "
          "scripts/freeze_study.py). Nothing was tagged or frozen here.")
    return 0


def cmd_reject(a, con) -> int:
    props = {p["rowid"]: p for p in _db.proposals_for(con)}
    prop = props.get(a.id)
    if prop is None:
        return _refuse(f"no proposal {a.id}")
    if prop["status"] != "pending":
        return _refuse(f"proposal {a.id} is {prop['status']}")
    if _db.verdicts_for(con, a.id):
        return _refuse(f"proposal {a.id} already has a verdict")
    if not (a.reason or "").strip():
        return _refuse("rejection needs a written --reason")
    _db.add_verdict(con, a.id, "reject", a.reason.strip(), a.operator or "")
    con.commit()
    print(f"recorded rejection of proposal {a.id}")
    return 0


def cmd_list(a, con) -> int:
    for p in _db.proposals_for(con):
        verdicts = _db.verdicts_for(con, p["rowid"])
        reps = _db.replays_for(con, p["rowid"])
        edge = reps[-1]["result"].get("edge") if reps else None
        print(f"#{p['rowid']} [{p['track']}/{p['status']}] {p['issue'][:90]} "
              f"| replays={len(reps)} edge={edge} "
              f"| verdict={[v['decision'] for v in verdicts]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--memory-config",
                    default=str(ROOT / "config/preregistered_memory.yaml"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--file", required=True)
    s.add_argument("--memory-db", default=None)
    s.add_argument("--traces-db", default=None)
    r = sub.add_parser("replay")
    r.add_argument("--id", type=int, required=True)
    r.add_argument("--memory-db", required=True)
    r.add_argument("--as-of", default=None)
    v = sub.add_parser("approve")
    v.add_argument("--id", type=int, required=True)
    v.add_argument("--reason", default=None)
    v.add_argument("--override", default=None)
    v.add_argument("--operator", default="")
    v.add_argument("--out", default=None)
    j = sub.add_parser("reject")
    j.add_argument("--id", type=int, required=True)
    j.add_argument("--reason", default=None)
    j.add_argument("--operator", default="")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    con = sqlite3.connect(a.db)
    try:
        con.executescript(_db.SCHEMA)
        if a.cmd == "submit":
            return cmd_submit(a, con)
        if a.cmd == "replay":
            return cmd_replay(a, con)
        if a.cmd == "approve":
            return cmd_approve(a, con)
        if a.cmd == "reject":
            return cmd_reject(a, con)
        return cmd_list(a, con)
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
