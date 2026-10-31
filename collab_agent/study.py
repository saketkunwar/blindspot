"""Study a pull with the frozen September rules. No scoring code lives
here: this module calls the same frozen path the live page used
(role-building, ledger spec, mechanism scores, v4 signature), then compares
against the frozen brief. Anything that disagrees with the frozen ranking
is reported, never adjusted.
"""
import json
import pathlib
import sqlite3

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

from engine.ledger import compute_ledger_from_spec, score_mechanisms  # noqa: E402
from engine import memory as _memory  # noqa: E402
from scripts import backtest_episodes as be  # noqa: E402
from store import db as _db  # noqa: E402


def score(rows: list[dict]) -> dict:
    """Score pull rows. Returns ledger, ranking, signature id, frozen-match
    flag, and the memory pattern match (episodes/labelled/known)."""
    dets = [(r["acq_date"], float(r["longitude"]), float(r["latitude"]))
            for r in rows]
    roles, _ = be._build_roles(dets, 0.5, 3)
    rules = json.loads((ROOT / "demo/fire_study/rules.json").read_text())
    ledger = compute_ledger_from_spec(rules, roles)
    ranking = score_mechanisms(rules, ledger)
    frozen = json.loads(
        (ROOT / "demo/fire_study/output/brief.json").read_text())
    same = ([m["id"] for m in ranking] ==
            [m["id"] for m in frozen["mechanisms"]] and
            all(abs(a["probability"] - b["probability"]) < 0.00005
                for a, b in zip(ranking, frozen["mechanisms"])))
    mem_cfg = yaml.safe_load(
        (ROOT / "config/preregistered_memory.yaml").read_text())
    edges = mem_cfg["signature"]["count_bin_edges"]
    sig = _memory.signature_for_facts(ledger["facts"], edges)
    match = {"episodes": 0, "labelled": 0, "known": False}
    mdb = ROOT / "results" / "memory_episodes.sqlite3"
    try:
        con = sqlite3.connect(f"file:{mdb.resolve()}?mode=ro", uri=True)
        try:
            eps = _db.episodes_for(con)
            outs = _db.outcomes_for(con)
        finally:
            con.close()
        as_of = max(o["window_end"] for o in outs
                    if o["label"] != "unlabelable")
        supports = mem_cfg["memory"]["outcome_supports"]
        rule_id = mem_cfg.get("rule_id", "memory-v1")
        pats = _memory.patterns_from_rows(
            eps, outs, edges, supports, as_of, rule_id)
        p = pats.get(sig["id"])
        if p is not None:
            match = {"episodes": p["episodes"], "labelled": p["labeled"],
                     "known": True}
    except (OSError, sqlite3.Error):
        pass
    return {"ledger": ledger, "ranking": ranking, "signature": sig["id"],
            "matches_frozen": same, "pattern_match": match}
