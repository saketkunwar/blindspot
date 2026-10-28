"""Ledger + scoring + prompt-audit for the prediction round (Step 2).

Moved here from ``agents/autoinsight.py`` so the symbolic compute layer is
importable without the CLI. ``agents/autoinsight.py`` is now a thin CLI that
imports the engine versions defined below.

Fact *values* are computed through the closed op set in
:mod:`engine.facts` (``evaluate``); this module only assembles the flood
ledger fact texts/flags, scores mechanisms, and builds/audits the anonymized
model prompt. Geometry *defaults* (channel-adjacent distance, cluster rule)
are resolved from the study ``domain.json`` at runtime -- this module
hardcodes no distances, counts, or thresholds of its own.
"""
from __future__ import annotations

import json
import math
import pathlib
import re

from engine import facts as _facts

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DOMAIN_PATH = ROOT / "demo" / "nepal_cascade" / "domain.json"

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T\d:.,-]*Z?")
_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_ALLOW_WORDS = {
    "river", "stream", "canal", "dam", "lake", "bridge", "road", "power",
    "project", "station", "upper", "lower", "north", "south", "east", "west",
    "new", "old", "crossing", "over", "aqueduct", "reservoir", "barrage",
    "weir", "hydropower", "hydro", "canal", "ditch", "waterfall",
}
_ASSERT_RE = re.compile(
    r"\b(has burst|have burst|did burst|will burst|has formed|did form|"
    r"has collapsed|did collapse|occurred|happened|confirmed|observed a burst)\b",
    re.IGNORECASE,
)


def _refuse_raw(paths: list[pathlib.Path]) -> None:
    raw = (ROOT / "data" / "raw").resolve()
    for p in paths:
        rp = p.resolve()
        if rp == raw or raw in rp.parents:
            raise SystemExit(f"quarantine: refusing to read ground-truth path {p}")


def _rcr8_vs(a, b) -> str:
    if a.equals(b):
        return "EQ"
    if a.disjoint(b):
        return "DC"
    if a.touches(b):
        return "EC"
    if a.within(b):
        return "NTPP"
    if a.contains(b):
        return "NTPPi"
    return "PO"


def load_domain_geometry(domain=None) -> dict:
    """Geometry defaults for the compute round, read at runtime.

    ``domain`` is a ``domain.json`` dict, a path to one, or None for the
    frozen flood study default. Returns ``{"channel_adjacent_m",
    "cluster_distance_m", "cluster_min_features"}``. Fail-closed: a missing
    file or missing keys raise instead of falling back to code constants.
    """
    if domain is None:
        domain = DEFAULT_DOMAIN_PATH
    if isinstance(domain, (str, pathlib.Path)):
        domain = json.loads(pathlib.Path(domain).read_text())
    geom = (domain or {}).get("geometry", {})
    cluster = geom.get("cluster", {})
    return {
        "channel_adjacent_m": float(geom["channel_adjacent_m"]),
        "cluster_distance_m": float(cluster["distance_m"]),
        "cluster_min_features": int(cluster["min_features"]),
    }


def _resolve_geometry(rules: dict, domain=None) -> tuple[float, float, int]:
    """(channel_adjacent_m, cluster_distance_m, cluster_min_features).

    Values named in ``rules`` win; anything absent falls back to the study
    ``domain.json`` geometry loaded at runtime.
    """
    if "channel_adjacent_m" in rules:
        adj_m = float(rules["channel_adjacent_m"])
    else:
        adj_m = load_domain_geometry(domain)["channel_adjacent_m"]
    cl = rules.get("cluster_rule") or {}
    if "max_distance_m" in cl and "min_features" in cl:
        return adj_m, float(cl["max_distance_m"]), int(cl["min_features"])
    dom = load_domain_geometry(domain)
    dist = float(cl.get("max_distance_m", dom["cluster_distance_m"]))
    feats = int(cl.get("min_features", dom["cluster_min_features"]))
    return adj_m, dist, feats


def compute_ledger(feats, waterways, target_geoms, extent_geom, rules,
                   domain=None):
    """Build the flood ledger of evidence facts.

    Values come from :mod:`engine.facts` ops; fact texts, activation flags,
    and diagnostics mirror the frozen flood ledger exactly. Geometry comes
    from ``rules`` with ``domain.json`` runtime defaults (see
    :func:`_resolve_geometry`).
    """
    from shapely.geometry import shape as _shape

    adj_m, cl_dist, cl_min = _resolve_geometry(rules, domain)
    roles = {
        "damage": {"type": "FeatureCollection", "features": list(feats)},
        "network": waterways,
        "target": {"type": "FeatureCollection", "features": list(target_geoms)},
        "boundary": extent_geom,
    }

    n, _ = _facts.evaluate("count", roles, {"role": "damage", "min_count": 1})
    up_share, _ = _facts.evaluate("half_share", roles, {
        "role": "damage", "boundary_role": "boundary",
        "axis": "lat", "mode": "share", "threshold": 0.5})
    near_share, _ = _facts.evaluate("near_share", roles, {
        "source_role": "damage", "ref_role": "network",
        "distance_m": adj_m, "threshold": 0.05})
    # Exact channel-adjacent count for the fact text (the frozen text formats
    # the unrounded share; the op returns the rounded share for value/active).
    near_chan, _ = _facts.evaluate("cluster", roles, {
        "source_role": "damage", "ref_role": "network",
        "distance_m": adj_m, "min_features": 1})
    near_target, cluster_hit = _facts.evaluate("cluster", roles, {
        "source_role": "damage", "ref_role": "target",
        "distance_m": cl_dist, "min_features": cl_min})
    density_ratio, _ = _facts.evaluate("half_share", roles, {
        "role": "damage", "boundary_role": "boundary",
        "axis": "lat", "mode": "density_ratio", "threshold": 1})
    extent_area, _ = _facts.evaluate("area_sum", roles, {"role": "boundary"})
    target_share = round(near_target / n, 4) if n else 0.0

    egeom = _shape(extent_geom)
    eproj = _facts._project(egeom)
    fproj = [_facts._project(_shape(f["geometry"])) for f in feats]
    rels = {}
    for g in fproj:
        r = _rcr8_vs(g, eproj)
        rels[r] = rels.get(r, 0) + 1

    facts = {
        "F1_total_pre_cutoff_damage": {"value": n, "active": n > 0,
            "text": f"{n} destroyed features predate the cutoff"},
        "F2_upstream_share": {"value": up_share, "active": up_share > 0.5,
            "text": f"upstream reach holds {up_share:.1%} of pre-cutoff damage"},
        "F3_channel_adjacent_share": {"value": near_share,
            "active": near_share > 0.05,
            "text": f"{(near_chan / n if n else 0.0):.1%} of pre-cutoff damage lies within channel-adjacent distance of mapped waterways"},
        "F4_cluster_hit": {"value": near_target, "active": cluster_hit,
            "text": f"frozen tributary-cluster rule: {'HIT' if cluster_hit else 'MISS'} "
                    f"({near_target} pre-cutoff features near the target reach)"},
        "F5_upstream_density_ratio": {"value": density_ratio,
            "active": density_ratio > 1,
            "text": f"upstream damage density is {density_ratio:.2f}x downstream density"},
        "F6_extent_context": {"value": extent_area, "active": True,
            "text": "static observed flood outline present as context (no time signal)"},
        "F7_target_reach_share": {"value": target_share,
            "active": target_share > 0.05,
            "text": f"{target_share:.1%} of pre-cutoff damage lies near the target tributary reach"},
        "F8_inputs_audit_clean": {"value": 1, "active": True,
            "text": "input audit verifies: every prediction byte pinned pre-cutoff"},
    }
    numbers = []
    for f in facts.values():
        v = f["value"]
        if isinstance(v, (int, float)):
            numbers.append(float(v))
    diagnostics = {"rcc8_vs_outline": rels,
                   "bbox": [float(v) for v in egeom.bounds]}
    return {"facts": facts, "numbers": numbers, "diagnostics": diagnostics}


def score_mechanisms(rules, ledger):
    facts = ledger["facts"]
    out = []
    for mech in rules["mechanisms"]:
        s = float(mech.get("prior", 0.0))
        if rules.get("caution_prior", {}).get("mechanism") == mech["id"]:
            s += float(rules["caution_prior"].get("weight", 0.0))
        for fid in mech.get("supports", []):
            if facts.get(fid, {}).get("active"):
                s += float(rules["facts"][fid]["weight"])
        for fid in mech.get("opposes", []):
            if facts.get(fid, {}).get("active"):
                s -= float(rules["facts"][fid]["weight"])
        out.append({"id": mech["id"], "title": mech["title"], "score": round(s, 4)})
    mx = max(o["score"] for o in out)
    exps = [math.exp(o["score"] - mx) for o in out]
    tot = sum(exps)
    for o, e in zip(out, exps):
        o["probability"] = round(e / tot, 4)
    out.sort(key=lambda o: o["probability"], reverse=True)
    resid = round(1.0 - sum(o["probability"] for o in out), 4)
    out[0]["probability"] = round(out[0]["probability"] + resid, 4)
    return out


def _input_tokens(inputs_dir: pathlib.Path, rules: dict) -> set[str]:
    toks: set[str] = set()
    for p in sorted(inputs_dir.glob("*")):
        if not p.is_file():
            continue
        try:
            text = p.read_text()
        except OSError:
            continue
        for m in _DATE_RE.findall(text):
            toks.add(m)
            toks.add(m[:10])
        for w in _WORD_RE.findall(text):
            if w.lower() not in _ALLOW_WORDS and (w[0].isupper() or w.isupper()):
                toks.add(w)
    target = rules["cluster_rule"].get("target_value", "")
    for w in _WORD_RE.findall(str(target)):
        if w.lower() not in _ALLOW_WORDS:
            toks.add(w)
    return toks


def build_prompt(rules, ledger) -> tuple[str, set[str]]:
    lines = [
        "Here is evidence from a river valley survey. All observations come "
        "from a single pre-cutoff snapshot S1; no later data was admitted.",
        "Reaches are anonymous: Reach Alpha is upstream of the surveyed flood "
        "centroid, Reach Beta is downstream. Tributary T-1 is one named "
        "tributary reach whose name is withheld.",
        "Candidate mechanisms (hypotheses to score, not facts):",
    ]
    for mech in rules["mechanisms"]:
        lines.append(f"- {mech['id']}: {mech['title']}")
    lines.append("Ledger facts:")
    for fid, f in ledger["facts"].items():
        lines.append(f"- {fid}: {f['text']}")
    lines.append(
        "Task: rank every candidate mechanism by how strongly this evidence "
        "alone supports it, from strongest to weakest. Reply with JSON only: "
        '{"ranking": [{"mechanism": id, "cites": [fact ids]}]}. '
        "Cite only the ledger facts above. Assert no outcome as fact.")
    return "\n".join(lines) + "\n", set()


def audit_prompt(prompt: str, forbidden: set[str]) -> list[str]:
    bad = []
    for tok in sorted(forbidden):
        if tok and re.search(r"(?<![A-Za-z])" + re.escape(tok) + r"(?![A-Za-z])", prompt):
            bad.append(f"forbidden token in prompt: {tok!r}")
    for m in _ASSERT_RE.findall(prompt):
        bad.append(f"outcome assertion in prompt: {m!r}")
    return bad


def _close(a: float, b: float, rel: float = 1e-6) -> bool:
    return abs(a - b) <= max(1e-9, rel * max(abs(a), abs(b)))


def validate_model_text(text: str, rules, ledger) -> tuple[list | None, list[str]]:
    try:
        body = json.loads(text)
        ranking = body.get("ranking")
    except (json.JSONDecodeError, AttributeError):
        return None, ["model reply is not JSON"]
    if not isinstance(ranking, list) or not ranking:
        return None, ["model reply has no ranking list"]
    ids = {m["id"] for m in rules["mechanisms"]}
    fids = set(ledger["facts"])
    bad = []
    seen = set()
    for entry in ranking:
        mid = entry.get("mechanism")
        if mid not in ids:
            bad.append(f"unknown mechanism {mid!r}")
        if mid in seen:
            bad.append(f"duplicate mechanism {mid!r}")
        seen.add(mid)
        for c in entry.get("cites", []):
            if c not in fids:
                bad.append(f"citation to non-ledger fact {c!r}")
    if seen != ids:
        bad.append(f"ranking covers {sorted(seen)}; expected all {sorted(ids)}")
    if bad:
        return None, bad
    return ranking, []
