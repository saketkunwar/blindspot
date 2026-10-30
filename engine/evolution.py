"""BlindSpot self-evolution discipline (M3): proposals, checks, replay.

The agent may propose, test, and wait for a human — it may never apply.
A proposal is a structured record with exactly one change; a human verdict
with a written reason is the only thing that can move it toward the rules,
and application always copies into a new version directory under a new tag
(never edits in place). Candidates name an issue with evidence but carry no
complete change; approving a candidate is refused.

All functions here are pure (plain data in, verdicts out) except the two
marked helpers, which only read. Track B opens weight-only: any other
change kind is rejected as unsupported, not silently held.
"""
from __future__ import annotations

import copy
import hashlib
import json

__all__ = [
    "validate_proposal",
    "cap_proposals",
    "independent_cutoffs",
    "time_slices",
    "apply_weight_change",
    "skeptic_replay",
]

_STOP_REASONS = ("satisfied", "failed_checks")


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def validate_proposal(prop: dict, known_episodes: set, known_traces: set,
                      evolver_cfg: dict, base_rules_shas: dict) -> list:
    """Structural checks on a pending proposal. Returns violations (empty
    ok). Candidates are not submittable: approving one is refused upstream,
    and this check rejects them too so they can never slip into review."""
    bad = []
    if prop.get("status") != "pending":
        return ["only pending proposals are reviewable "
                f"(got {prop.get('status')!r})"]
    if prop.get("track") not in ("A", "B"):
        bad.append(f"unknown track {prop.get('track')!r}")
    change = prop.get("change") or {}
    if not isinstance(change, dict) or len(change) != 1:
        return bad + ["a proposal holds exactly one change"]
    (kind, body), = change.items()
    if kind not in (evolver_cfg.get("supported_change_kinds") or []):
        bad.append(f"unsupported change kind {kind!r} "
                   "(Track B opens weight-only)")
    elif kind == "weight":
        if set(body or {}) != {"fact_id", "old_weight", "new_weight"}:
            bad.append("weight change needs fact_id/old_weight/new_weight")
        else:
            try:
                old_w, new_w = float(body["old_weight"]), float(body["new_weight"])
            except (TypeError, ValueError):
                bad.append("weight change weights must be numbers")
            else:
                if old_w == new_w:
                    bad.append("weight change leaves the value unchanged")
                if old_w < 0 or new_w < 0:
                    bad.append("weight change weights must be non-negative")
    if not (prop.get("issue") or "").strip():
        bad.append("proposal needs a written issue")
    try:
        rec = int(prop.get("recurrence", 0))
    except (TypeError, ValueError):
        bad.append("recurrence must be an integer")
    else:
        if rec < int(evolver_cfg.get("min_recurrence", 1)):
            bad.append(f"recurrence {rec} below bar "
                       f"{evolver_cfg.get('min_recurrence')}")
    missing_eps = [e for e in (prop.get("cited_episodes") or [])
                   if e not in known_episodes]
    if missing_eps:
        bad.append(f"cited episodes do not exist: {missing_eps[:3]}")
    missing_tr = [t for t in (prop.get("cited_traces") or [])
                  if t not in known_traces]
    if missing_tr:
        bad.append(f"cited traces do not exist: {missing_tr[:3]}")
    if prop.get("track") == "B":
        base = (prop.get("base_rules_sha") or "")
        if base not in (base_rules_shas or {}).values():
            bad.append("base_rules_sha matches no frozen rules file")
    if not isinstance(prop.get("rejected"), list):
        bad.append("rejected must be a list (possibly empty)")
    return bad


def cap_proposals(candidates: list, cap: int) -> tuple:
    """Enforce the per-run proposal cap. Returns (kept, dropped_count)."""
    cap = max(1, int(cap))
    return candidates[:cap], max(0, len(candidates) - cap)


def independent_cutoffs(cutoffs: list, gap_days: int) -> list:
    """Greedy independent set, oldest first: keep a cutoff only when it is
    at least ``gap_days`` past every kept one. Neighboring slides share
    most of their data and must not each count toward recurrence."""
    from datetime import date as _date
    kept = []
    for c in sorted(set(cutoffs)):
        day = _date.fromisoformat(c)
        if all(abs((day - _date.fromisoformat(k)).days) >= gap_days
               for k in kept):
            kept.append(c)
    return kept


def time_slices(cutoffs: list, propose_frac: float,
                validate_frac: float) -> dict:
    """Split sorted cutoffs old-to-new into propose/validate/final spans.

    Boundaries fall on day gaps (never inside a day): the propose span ends
    at the last cutoff within the first fraction of the observed span, the
    validate span at the last cutoff within the first two fractions, and
    the final slice is everything later — selection never touches it.
    """
    from datetime import date as _date, timedelta as _td
    days = sorted(set(cutoffs))
    if len(days) < 3:
        return {"propose": days, "validate": [], "final": []}
    lo = _date.fromisoformat(days[0])
    span = (_date.fromisoformat(days[-1]) - lo).days or 1
    p_end = lo + _td(days=int(span * propose_frac))
    v_end = lo + _td(days=int(span * (propose_frac + validate_frac)))
    out = {"propose": [], "validate": [], "final": []}
    for d in days:
        day = _date.fromisoformat(d)
        out["propose" if day <= p_end else
            "validate" if day <= v_end else "final"].append(d)
    if not out["validate"]:
        out["validate"] = out["propose"][-1:]
    return out


def apply_weight_change(base_rules: dict, change: dict) -> dict:
    """Copy the rules with one fact weight replaced. The input is never
    mutated; the old weight must match or the change fails loudly (the
    world moved under the proposal)."""
    body = change["weight"]
    facts = (base_rules.get("facts") or {})
    if body["fact_id"] not in facts:
        raise KeyError(f"unknown fact {body['fact_id']!r}")
    if float(facts[body["fact_id"]].get("weight")) != float(body["old_weight"]):
        raise ValueError("old_weight disagrees with the base rules")
    new_rules = copy.deepcopy(base_rules)
    new_rules["facts"][body["fact_id"]]["weight"] = float(body["new_weight"])
    return new_rules


def skeptic_replay(base_rules: dict, change: dict, episodes: list,
                   outcomes: dict, supports: dict, roles_fn) -> dict:
    """Deterministic replay: frozen rules versus the proposed change on the
    given episodes. Scores each side by how often its top story is backed
    by the episode's outcome label. Returns the comparison for a human to
    decide on, with this evidence on record.

    ``episodes`` are rows with episode_id/cutoff; ``outcomes`` maps
    episode_id to label; ``roles_fn(episode)`` rebuilds that episode's
    ledger roles from pinned inputs (injected so tests need no data).
    """
    from engine.ledger import compute_ledger_from_spec, score_mechanisms
    proposed_rules = apply_weight_change(base_rules, change)
    base_shas = hashlib.sha256(_canon(base_rules).encode()).hexdigest()[:12]
    tallies = {"episodes": 0, "base_hits": 0, "proposed_hits": 0,
               "base_rules_sha": base_shas, "moved_tops": []}
    for ep in episodes:
        label = outcomes.get(ep["episode_id"])
        if label is None:
            continue
        roles = roles_fn(ep)
        base_top = score_mechanisms(
            base_rules, compute_ledger_from_spec(base_rules, roles))[0]["id"]
        prop_top = score_mechanisms(
            proposed_rules,
            compute_ledger_from_spec(proposed_rules, roles))[0]["id"]
        backed = set(supports.get(label, []))
        tallies["episodes"] += 1
        tallies["base_hits"] += base_top in backed
        tallies["proposed_hits"] += prop_top in backed
        if prop_top != base_top:
            tallies["moved_tops"].append(
                {"episode": ep["episode_id"], "was": base_top,
                 "now": prop_top})
    n = tallies["episodes"] or 1
    tallies["base_rate"] = tallies["base_hits"] / n
    tallies["proposed_rate"] = tallies["proposed_hits"] / n
    tallies["edge"] = tallies["proposed_rate"] - tallies["base_rate"]
    return tallies
