"""BlindSpot tiered-memory read path (M1): patterns and score adjustment.

Memory is an additive, clearly labelled layer beside the frozen ranking,
never a replacement for it. Three rules keep it honest:

1. Memory off, empty, or below the speaking threshold means byte-identical
   output: the caller omits the memory section entirely.
2. Only the past may be read: every read takes an ``as_of`` day and keeps
   only labelled episodes whose outcome window ends on or before it. Every
   window ends after its own episode's cutoff by construction, so a row
   whose window is still open at ``as_of`` is knowledge the case could not
   have had yet.
3. Memory claims go through a check: the ledger carries a ``memory`` block
   of counts, and the section's sentences must restate exactly those
   numbers (see :func:`validate_memory_section`).

All functions here are pure (plain data in, plain data out) except the
small read helper, which opens the store read-only and selects only.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

__all__ = [
    "bin_count",
    "signature_for_facts",
    "patterns_from_rows",
    "memory_adjust",
    "memory_note",
    "validate_memory_section",
    "read_episodes_outcomes",
]

_AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_as_of(as_of: str) -> str:
    """Fail-closed ``as_of`` validation: accept an ISO day, reject the rest."""
    if not isinstance(as_of, str) or not _AS_OF_RE.match(as_of):
        raise ValueError(f"memory --as-of must be an ISO day, got {as_of!r}")
    return as_of


def bin_count(value: int, edges: list) -> int:
    """Bin index of an integer value: first bin whose edge exceeds it."""
    for i, edge in enumerate(edges):
        if value < edge:
            return i
    return len(edges)


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def _project_gap(value: dict, edges: list) -> list:
    """Project a gap-statistic dict to its pattern shape: the longest gap
    in whole days plus the binned distinct-day count. Raw counts, totals,
    and spans grow with every slice and would fingerprint each episode, so
    they stay out of the key. Dicts without these keys project to zeros
    (no gap evidence either way)."""
    try:
        gap_days = int(round(float(value.get("max_gap_s", 0)) / 86400))
    except (TypeError, ValueError):
        gap_days = 0
    try:
        distinct = int(value.get("n_distinct", 0))
    except (TypeError, ValueError):
        distinct = 0
    return [bin_count(gap_days, edges), bin_count(distinct, edges)]


def signature_for_facts(facts: dict, edges: list) -> dict:
    """Pattern signature of one ledger's facts.

    Returns ``{"id": <short hash>, "readable": <sorted tuple>}`` built from
    active facts only: each fact id paired with its binned count (integers
    and whole-number floats), its projected gap shape (dicts), or its
    verbatim value (booleans and strings, already categorical). Raw
    non-integral floats (areas, extents) are left out: they fingerprint a
    slice rather than describing a pattern, and the studies mark such
    facts context-only. Because the key is built from the ledger, every
    element of it can pass the verification gate; because everything
    numeric is binned or projected coarsely, slice growth alone cannot
    split a pattern in two.
    """
    items = []
    for fid in sorted(facts):
        f = facts[fid] or {}
        if not f.get("active"):
            continue
        v = f.get("value")
        if isinstance(v, bool):
            items.append([fid, v])
        elif isinstance(v, int):
            items.append([fid, bin_count(v, edges)])
        elif isinstance(v, float) and v.is_integer():
            items.append([fid, bin_count(int(v), edges)])
        elif isinstance(v, dict):
            items.append([fid, _project_gap(v, edges)])
        elif isinstance(v, str):
            items.append([fid, v])
        # Other raw floats are dropped (see docstring): fingerprints, not
        # patterns.
    return {"id": hashlib.sha256(_canon(items).encode()).hexdigest()[:16],
            "readable": items}


def patterns_from_rows(episodes: list, outcomes: list, edges: list,
                       supports: dict, as_of: str, rule_id: str) -> dict:
    """Derived pattern table: a pure function of stored rows, recomputed on
    demand, never stored. Keys are signature ids; values hold the signature,
    the episode count, the labelled count, and per-mechanism hits.

    Only rows for ``rule_id`` are read, and only labelled episodes whose
    outcome window ends on or before ``as_of``. Anything later is knowledge
    the case could not have had yet and is excluded, not averaged in.
    """
    check_as_of(as_of)
    label_of = {}
    for o in outcomes:
        if o.get("rule_id") == rule_id and o.get("label") not in (
                "unlabelable",):
            if o.get("window_end") and o["window_end"] <= as_of:
                label_of[o["episode_id"]] = o["label"]
    mechs = sorted({m for labels in supports.values() for m in labels})
    patterns = {}
    for ep in episodes:
        sig = signature_for_facts(ep.get("facts") or {}, edges)
        p = patterns.setdefault(
            sig["id"], {"signature": sig, "episodes": 0, "labeled": 0,
                        "labels": {}, "hits": {m: 0 for m in mechs}})
        p["episodes"] += 1
        label = label_of.get(ep.get("episode_id"))
        if label is None:
            continue
        p["labeled"] += 1
        p["labels"][label] = p["labels"].get(label, 0) + 1
        for m in supports.get(label, []):
            if m in p["hits"]:
                p["hits"][m] += 1
    return patterns


def memory_adjust(ranking: list, stats: dict | None, mem: dict) -> tuple:
    """Second ranking labelled ``memory_adjusted``, or ``(None, reason)``.

    For each mechanism the smoothed hit rate under the case's signature is
    ``(hits + alpha) / (labeled + 2 * alpha)``; the shift is that rate minus
    one half (no evidence either way), clamped to ``max_abs_shift``. Shifts
    are added to the frozen probabilities, clipped at zero, renormalized.
    The frozen ``ranking`` argument is never mutated. Returns ``(None,
    "not enough history")`` below ``min_episodes_to_speak`` — the caller
    then omits the section entirely.
    """
    need = int(mem["min_episodes_to_speak"])
    alpha = float(mem["smoothing_alpha"])
    cap = float(mem["max_abs_shift"])
    if stats is None or stats.get("labeled", 0) < need:
        return None, "not enough history"
    labeled = stats["labeled"]
    shifts = {}
    for m in [r["id"] for r in ranking]:
        rate = (stats["hits"].get(m, 0) + alpha) / (labeled + 2 * alpha)
        shift = rate - 0.5
        shifts[m] = max(-cap, min(cap, shift))
    moved = []
    for r in ranking:
        moved.append((r["id"], max(0.0, r["probability"] + shifts[r["id"]])))
    total = sum(p for _, p in moved) or 1.0
    adjusted = [{"id": m, "probability": p / total, "memory_shift": shifts[m],
                 "title": next(r["title"] for r in ranking if r["id"] == m)}
                for m, p in sorted(moved, key=lambda kv: -kv[1])]
    block = {"signature": stats["signature"]["id"],
             "episodes_seen": stats["episodes"],
             "episodes_labeled": labeled,
             "label_counts": stats["labels"],
             "hits": {m: stats["hits"].get(m, 0) for m in shifts},
             "shifts": shifts,
             "rule": {"min_episodes_to_speak": need, "smoothing_alpha": alpha,
                      "max_abs_shift": cap}}
    return adjusted, block


def memory_note(adjusted: list, block: dict) -> str:
    """The section's one human sentence, formatted from the block so the
    numbers in prose and the numbers in the ledger cannot disagree."""
    top = adjusted[0]
    return (f"Seen {block['episodes_seen']} times before "
            f"({block['episodes_labeled']} with known outcomes); "
            f"the '{top['id']}' story came true "
            f"{block['hits'].get(top['id'], 0)} of those times.")


def validate_memory_section(brief: dict) -> list:
    """Fail-closed check on a brief's memory section: the note's numbers
    must equal the ledger's memory block. Returns violations (empty ok).

    A brief with no memory section is valid — silence needs no check.
    """
    section = brief.get("memory")
    if not section:
        return []
    bad = []
    block = ((brief.get("ledger") or {}).get("memory") or {})
    note = section.get("note", "")
    try:
        seen = int(re.search(r"Seen (\d+) times before", note).group(1))
        lab = int(re.search(r"\((\d+) with known outcomes\)", note).group(1))
        hit = int(re.search(r"came true (\d+) of those times", note).group(1))
    except (AttributeError, ValueError):
        return ["memory note is not in the checkable sentence form"]
    if seen != block.get("episodes_seen"):
        bad.append("memory note episodes_seen disagrees with ledger block")
    if lab != block.get("episodes_labeled"):
        bad.append("memory note episodes_labeled disagrees with ledger block")
    top = (section.get("adjusted_mechanisms") or [{}])[0].get("id")
    if hit != (block.get("hits") or {}).get(top):
        bad.append("memory note hit count disagrees with ledger block")
    return bad


def read_episodes_outcomes(db_path: str) -> tuple:
    """Read-only episode/outcome rows. The file must already exist: memory
    never creates a store, and a missing file fails instead of passing an
    empty pattern table silently."""
    import pathlib
    from store import db as _db
    p = pathlib.Path(db_path)
    if not p.is_file():
        raise FileNotFoundError(f"memory db not found: {db_path}")
    con = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    try:
        return _db.episodes_for(con), _db.outcomes_for(con)
    finally:
        con.close()
