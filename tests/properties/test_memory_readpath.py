"""M1 memory read path: silence by default, honesty when speaking.

G19 (frozen identity): with an empty or below-threshold memory store the
brief carries no memory section at all — byte-identical to the frozen
baseline. G20 (leakage): only outcomes whose window closed on/before as_of
are readable; the adjust math is capped, renormalized, and never mutates
the frozen ranking; the section's sentences must restate the ledger block.
"""
import json
import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine import memory as mem  # noqa: E402
from scripts import backtest_episodes as be  # noqa: E402
from store import db  # noqa: E402

MEM = yaml.safe_load((ROOT / "config/preregistered_memory.yaml").read_text())
EDGES = MEM["signature"]["count_bin_edges"]
SUPPORTS = MEM["memory"]["outcome_supports"]
RULE = MEM["rule_id"]
FIRE_BRIEF = ROOT / "demo/fire_study/output/brief.json"


def _run_backtest(db_path, extra=()):
    argv = ["--db", str(db_path),
            "--rules", str(ROOT / "demo/fire_study/rules.json"),
            "--memory-config", str(ROOT / "config/preregistered_memory.yaml"),
            "--no-manifest-check", *extra]
    argv += ["--scene", str(ROOT / "data/fire_kalimantan/firms_kalimantan_c.json")]
    assert be.main(argv) == 0
    return db_path


def _run_brief(db_path, out_path, as_of):
    from agents import autoinsight as ai
    ai.run("demo/fire_study/inputs", "demo/fire_study/rules.json",
           str(out_path), str(out_path.parent / "prompts"),
           model_round="off",
           domain_path="demo/fire_study/domain.json",
           memory_db=str(db_path),
           memory_config=str(ROOT / "config/preregistered_memory.yaml"),
           as_of=as_of)


def _facts(**values):
    return {k: {"value": v, "active": True} for k, v in values.items()}


def test_signature_deterministic_and_binned():
    a = mem.signature_for_facts(_facts(FF1=6142, FF3=30), EDGES)
    b = mem.signature_for_facts(_facts(FF3=30, FF1=6142), EDGES)
    assert a == b
    # Same bin (both >= 1000): identical signature despite different counts.
    c = mem.signature_for_facts(_facts(FF1=5000, FF3=30), EDGES)
    assert c == a
    # Across a bin edge (30 -> 5): different signature.
    d = mem.signature_for_facts(_facts(FF1=6142, FF3=5), EDGES)
    assert d != a
    # Inactive facts never join the pattern.
    e = mem.signature_for_facts(
        {"FF1": {"value": 6142, "active": True},
         "FF9": {"value": 1, "active": False}}, EDGES)
    assert e == mem.signature_for_facts(_facts(FF1=6142), EDGES)


def _gap(n_dated, n_distinct, max_gap_s=1.0, span_s=1.0):
    return {"max_gap_s": max_gap_s, "n_dated": n_dated,
            "n_distinct": n_distinct, "n_total": n_dated, "span_s": span_s}


def test_signature_projects_gaps_and_drops_areas():
    """v4 key: gap dicts with the same day-gap and binned distinct days
    share a signature despite growing raw counts; raw areas never split one.
    """
    base = {"FF1": {"value": 500, "active": True},
            "FF5": {"value": _gap(587, 2), "active": True},
            "FF6": {"value": 1219840813331.4, "active": True}}
    grown = {"FF1": {"value": 900, "active": True},
             "FF5": {"value": _gap(1603, 2, span_s=2.0), "active": True},
             "FF6": {"value": 71918394940.6, "active": True}}
    # FF1 500 vs 900 share a bin; distinct days stay binned together while
    # raw counts and spans triple; the areas differ wildly and must not
    # matter.
    assert (mem.signature_for_facts(base, EDGES) ==
            mem.signature_for_facts(grown, EDGES))
    # A longer day-gap or a new distinct-day bin splits the pattern.
    split_gap = dict(base)
    split_gap["FF5"] = {"value": _gap(587, 2, max_gap_s=86400.0),
                        "active": True}
    assert (mem.signature_for_facts(split_gap, EDGES) !=
            mem.signature_for_facts(base, EDGES))
    split_days = dict(base)
    split_days["FF5"] = {"value": _gap(5000, 12), "active": True}
    assert (mem.signature_for_facts(split_days, EDGES) !=
            mem.signature_for_facts(base, EDGES))
    # Dicts without gap keys project to zeros, deterministically.
    odd = {"FFX": {"value": {"unrelated": [1, 2]}, "active": True}}
    assert (mem.signature_for_facts(odd, EDGES) ==
            mem.signature_for_facts(odd, EDGES))


def test_patterns_read_only_the_closed_past():
    eps = [{"episode_id": "s@2026-09-17", "facts": _facts(FF1=10)},
           {"episode_id": "s@2026-09-18", "facts": _facts(FF1=10)}]
    outs = [{"episode_id": "s@2026-09-17", "rule_id": RULE, "label": "restart",
             "window_start": "2026-09-18", "window_end": "2026-09-19"},
            {"episode_id": "s@2026-09-18", "rule_id": RULE, "label": "restart",
             "window_start": "2026-09-19", "window_end": "2026-09-20"}]
    pats = mem.patterns_from_rows(eps, outs, EDGES, SUPPORTS, "2026-09-19",
                                  RULE)
    (only,) = pats.values()
    assert only["episodes"] == 2
    assert only["labeled"] == 1  # the still-open window is not knowledge yet
    assert only["labels"] == {"restart": 1}
    # A wrong rule id labels nothing: episodes seen, zero usable history.
    wrong = mem.patterns_from_rows(eps, outs, EDGES, SUPPORTS, "2026-09-20",
                                    "other-rule")
    assert [p["labeled"] for p in wrong.values()] == [0]
    pats2 = mem.patterns_from_rows(eps, outs, EDGES, SUPPORTS, "2026-09-20",
                                   RULE)
    assert list(pats2.values())[0]["labeled"] == 2
    with pytest.raises(ValueError):
        mem.patterns_from_rows(eps, outs, EDGES, SUPPORTS, "soon", RULE)


def test_adjust_silent_below_threshold_and_pure():
    ranking = [{"id": "m1", "title": "M1", "probability": 0.7},
               {"id": "m2", "title": "M2", "probability": 0.3}]
    before = json.loads(json.dumps(ranking))
    adjusted, reason = mem.memory_adjust(ranking, None, MEM["memory"])
    assert adjusted is None and reason == "not enough history"
    thin = {"signature": {"id": "s"}, "episodes": 2, "labeled": 2,
            "labels": {"restart": 2}, "hits": {"m1": 2}}
    adjusted, _ = mem.memory_adjust(ranking, thin, MEM["memory"])
    assert adjusted is None
    assert ranking == before  # frozen ranking never mutated


def test_adjust_math_capped_renormalized_sorted():
    ranking = [{"id": "a", "title": "A", "probability": 0.5},
               {"id": "b", "title": "B", "probability": 0.3},
               {"id": "c", "title": "C", "probability": 0.2}]
    stats = {"signature": {"id": "s", "readable": []}, "episodes": 6,
             "labeled": 6, "labels": {"restart": 5, "quiet": 1},
             "hits": {"a": 5, "b": 0, "c": 1}}
    adjusted, block = mem.memory_adjust(
        ranking, stats, {"min_episodes_to_speak": 5, "smoothing_alpha": 1.0,
                         "max_abs_shift": 0.10})
    by_id = {r["id"]: r for r in adjusted}
    # a: (5+1)/(6+2) - 0.5 = +0.25 -> capped +0.10; b: (0+1)/8 - 0.5 -> -0.10.
    assert by_id["a"]["memory_shift"] == pytest.approx(0.10)
    assert by_id["b"]["memory_shift"] == pytest.approx(-0.10)
    assert abs(sum(r["probability"] for r in adjusted) - 1.0) < 1e-9
    assert [r["id"] for r in adjusted] == ["a", "b", "c"]
    assert all(r["probability"] >= 0 for r in adjusted)
    assert block["episodes_labeled"] == 6
    note = mem.memory_note(adjusted, block)
    assert "Seen 6 times before" in note and "(6 with known outcomes)" in note
    brief = {"ledger": {"memory": block},
             "memory": {"adjusted_mechanisms": adjusted, "note": note}}
    assert mem.validate_memory_section(brief) == []
    # No section needs no check; a tampered note fails it.
    assert mem.validate_memory_section({"ledger": {}}) == []
    bad = json.loads(json.dumps(brief))
    bad["memory"]["note"] = note.replace("Seen 6 times", "Seen 60 times")
    assert mem.validate_memory_section(bad) != []
    bad2 = json.loads(json.dumps(brief))
    bad2["ledger"]["memory"]["episodes_seen"] = 7
    assert mem.validate_memory_section(bad2) != []


def test_empty_memory_brief_is_frozen_brief(tmp_path):
    con = db.connect(tmp_path / "empty.sqlite3")
    con.close()
    out = tmp_path / "brief.json"
    _run_brief(tmp_path / "empty.sqlite3", out, "2026-09-20")
    assert out.read_bytes() == FIRE_BRIEF.read_bytes()


def test_below_threshold_memory_brief_is_frozen_brief(tmp_path):
    # The real census (2 labelable < 5 to speak) stays silent: no section.
    dbp = _run_backtest(tmp_path / "small.sqlite3")
    out = tmp_path / "brief.json"
    _run_brief(dbp, out, "2026-09-20")
    assert out.read_bytes() == FIRE_BRIEF.read_bytes()
    assert "memory" not in json.loads(out.read_text())


def test_pruned_future_brief_matches_full_brief(tmp_path):
    # G20 at test level: deleting every row a case could not know yet
    # leaves the brief byte-identical.
    import shutil
    import sqlite3
    full = _run_backtest(tmp_path / "full.sqlite3")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _run_brief(full, a, "2026-09-18")
    pruned = tmp_path / "pruned.sqlite3"
    shutil.copy(full, pruned)
    con = sqlite3.connect(pruned)
    try:
        n_ep = con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        con.execute("DELETE FROM outcomes WHERE window_end > '2026-09-18'")
        con.execute("DELETE FROM episodes WHERE cutoff > '2026-09-18'")
        con.commit()
        n_left = con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    finally:
        con.close()
    assert n_left < n_ep and n_left > 0
    _run_brief(pruned, b, "2026-09-18")
    assert a.read_bytes() == b.read_bytes()


def test_memory_flags_fail_closed(tmp_path):
    from agents import autoinsight as ai
    out = tmp_path / "brief.json"
    with pytest.raises(SystemExit):  # --as-of missing
        ai.run("demo/fire_study/inputs", "demo/fire_study/rules.json",
               str(out), str(tmp_path), model_round="off",
               domain_path="demo/fire_study/domain.json",
               memory_db=str(tmp_path / "nope.sqlite3"),
               memory_config=str(ROOT / "config/preregistered_memory.yaml"),
               as_of=None)
    with pytest.raises(SystemExit):  # bad --as-of
        ai.run("demo/fire_study/inputs", "demo/fire_study/rules.json",
               str(out), str(tmp_path), model_round="off",
               domain_path="demo/fire_study/domain.json",
               memory_db=str(tmp_path / "nope.sqlite3"),
               memory_config=str(ROOT / "config/preregistered_memory.yaml"),
               as_of="someday")
    with pytest.raises(FileNotFoundError):  # missing store never created
        mem.read_episodes_outcomes(str(tmp_path / "nope.sqlite3"))
    assert not (tmp_path / "nope.sqlite3").exists()


def _ep(epid, facts=None, scene="s", cutoff="2026-09-18",
       top="suppression_then_restart", n_pre=10):
    return {"episode_id": epid, "scene": scene, "cutoff": cutoff,
            "facts": facts if facts is not None else _facts(FF1=10),
            "top_mechanism": top, "n_pre": n_pre, "cells_pre": 3}


def _out(epid, label="restart", start="2026-09-19", end="2026-09-20",
         n_post=9):
    return {"episode_id": epid, "rule_id": RULE, "label": label,
            "window_start": start, "window_end": end, "n_post": n_post}


def test_recall_returns_nearest_labelled_first():
    eps = [_ep("s@2026-09-18", _facts(FF1=10)),
           _ep("s@2026-09-19", _facts(FF1=5)),
           _ep("s@2026-09-20", _facts(FF9=7))]
    outs = [_out("s@2026-09-18"), _out("s@2026-09-19"), _out("s@2026-09-20")]
    rec = mem.nearest_cases(_facts(FF1=10), eps, outs, EDGES, RULE,
                            "2026-09-22", 5)
    got = [(c["episode_id"], c["distance"]) for c in rec["cases"]]
    assert got == [("s@2026-09-18", 0), ("s@2026-09-19", 1),
                   ("s@2026-09-20", 2)]
    first = rec["cases"][0]
    assert first["differing"] == []
    assert rec["cases"][1]["differing"] == ["FF1"]
    for c in rec["cases"]:
        for k in ("episode_id", "scene", "cutoff", "window_start",
                  "window_end", "label", "n_pre", "n_post",
                  "top_mechanism", "distance", "differing"):
            assert k in c
    # Deterministic and capped.
    again = mem.nearest_cases(_facts(FF1=10), eps, outs, EDGES, RULE,
                              "2026-09-22", 2)
    assert [c["episode_id"] for c in again["cases"]] == \
        ["s@2026-09-18", "s@2026-09-19"]
    assert mem.nearest_cases(_facts(FF1=10), eps, outs, EDGES, RULE,
                             "2026-09-22", 5) == rec


def test_recall_reads_only_the_closed_past():
    eps = [_ep("s@2026-09-18", _facts(FF1=10)),
           _ep("s@2026-09-19", _facts(FF1=10))]
    outs = [_out("s@2026-09-18", end="2026-09-20"),
            _out("s@2026-09-19", end="2026-09-25")]
    rec = mem.nearest_cases(_facts(FF1=10), eps, outs, EDGES, RULE,
                            "2026-09-20", 5)
    assert [c["episode_id"] for c in rec["cases"]] == ["s@2026-09-18"]
    # The still-open same-shape window is counted, never shown as known.
    assert rec["unlabelled_same_shape"] == 1
    with pytest.raises(ValueError):
        mem.nearest_cases(_facts(FF1=10), eps, outs, EDGES, RULE, "soon", 5)
    empty = mem.nearest_cases(_facts(FF1=10), eps, outs, EDGES,
                              "other-rule", "2026-09-25", 5)
    assert empty["cases"] == []


def test_status_memory_table_reads_store(tmp_path):
    from scripts import status as st
    dbp = _run_backtest(tmp_path / "mem.sqlite3")
    rows = st.memory_table(ROOT, str(dbp))
    assert rows, "expected pattern rows from the real census"
    assert all(len(r) == 4 for r in rows)
    assert sum(int(r[1]) for r in rows) == 4
    assert st.memory_table(ROOT, None) == []
    assert st.memory_table(ROOT, str(tmp_path / "missing.sqlite3")) == []
