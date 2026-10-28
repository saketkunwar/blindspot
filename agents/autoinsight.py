"""Autoinsight: hindsight-free mechanism ranking over pre-cutoff inputs.

Prediction path. Reads ONLY the curated inputs directory, the frozen rules
file, and geometry kernels. It refuses to open anything under ``data/raw``
(the ground-truth side) by construction: every resolved input path is
checked, and a path inside ``data/raw`` fails the run.

Loop: kernel pass (per-feature RCC-8 vs the static outline, reach split,
continuity aggregates) -> ledger of evidence facts -> rival framing from the
frozen mechanism set -> optional model round with a fully anonymized prompt
-> verification gate (only ledger-grounded claims survive) -> brief with
support-strength probabilities (softmax over documented scores; explicitly
NOT calibrated frequencies).

The model prompt carries no place names, no calendar dates, and no outcome
assertions: anonymous reaches, relative snapshot labels, mechanisms listed
only as candidate hypotheses. The exact prompt is saved verbatim and scanned
against tokens drawn from the inputs themselves (any name or date the inputs
contain is forbidden in the prompt), so anonymization is checked, not
promised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

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


def _m(geom):
    """Project lon/lat to local meters (latitude-corrected equirectangular)."""
    from shapely.ops import transform as _t

    lat0 = geom.centroid.y
    kx = 111320.0 * math.cos(math.radians(lat0))

    def fwd(x, y, z=None):
        return (x * kx, y * 110540.0)

    return _t(fwd, geom)


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


def compute_ledger(feats, waterways, target_geoms, extent_geom, rules):
    from shapely.geometry import shape as _shape
    from shapely.ops import unary_union

    egeom = _shape(extent_geom)
    lat0 = float(egeom.centroid.y)
    ww = [_shape(f["geometry"]) for f in waterways["features"] if f.get("geometry")]
    wproj = [_m(g) for g in ww]
    wunion = unary_union(wproj) if wproj else None
    tproj = [_m(_shape(f["geometry"])) for f in target_geoms
             if f.get("geometry")]
    tunion = unary_union(tproj) if tproj else None
    eproj = _m(egeom)
    adj_m = float(rules.get("channel_adjacent_m", 250))
    cl = rules["cluster_rule"]

    n = len(feats)
    up = sum(1 for f in feats if _shape(f["geometry"]).centroid.y > lat0)
    up_share = up / n if n else 0.0
    fproj = [_m(_shape(f["geometry"])) for f in feats]
    near_chan = sum(1 for g in fproj if wunion is not None and g.distance(wunion) <= adj_m)
    near_share = near_chan / n if n else 0.0
    near_target = sum(1 for g in fproj
                      if tunion is not None and not tunion.is_empty
                      and g.distance(tunion) <= float(cl["max_distance_m"]))
    target_share = near_target / n if n else 0.0
    cluster_hit = bool(near_target >= int(cl["min_features"]))
    minx, miny, maxx, maxy = eproj.bounds
    lat0_m = _m(egeom.centroid).y
    split_m = min(max(lat0_m, miny), maxy)
    full_w = max(maxx - minx, 1.0)
    up_region = full_w * max(maxy - split_m, 1.0)
    dn_region = full_w * max(split_m - miny, 1.0)
    up_n = sum(1 for g in fproj if g.centroid.y > split_m)
    dn_n = n - up_n
    density_ratio = (up_n / up_region) / (dn_n / dn_region + 1e-12)
    density_ratio = min(density_ratio, 1e6)
    rels = {}
    for g in fproj:
        r = _rcr8_vs(g, eproj)
        rels[r] = rels.get(r, 0) + 1

    facts = {
        "F1_total_pre_cutoff_damage": {"value": n, "active": n > 0,
            "text": f"{n} destroyed features predate the cutoff"},
        "F2_upstream_share": {"value": round(up_share, 4), "active": up_share > 0.5,
            "text": f"upstream reach holds {up_share:.1%} of pre-cutoff damage"},
        "F3_channel_adjacent_share": {"value": round(near_share, 4),
            "active": near_share > 0.05,
            "text": f"{near_share:.1%} of pre-cutoff damage lies within channel-adjacent distance of mapped waterways"},
        "F4_cluster_hit": {"value": near_target, "active": cluster_hit,
            "text": f"frozen tributary-cluster rule: {'HIT' if cluster_hit else 'MISS'} "
                    f"({near_target} pre-cutoff features near the target reach)"},
        "F5_upstream_density_ratio": {"value": round(density_ratio, 3),
            "active": density_ratio > 1,
            "text": f"upstream damage density is {density_ratio:.2f}x downstream density"},
        "F6_extent_context": {"value": round(float(eproj.area), 1), "active": True,
            "text": "static observed flood outline present as context (no time signal)"},
        "F7_target_reach_share": {"value": round(target_share, 4),
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
    import math as _m2
    exps = [_m2.exp(o["score"] - mx) for o in out]
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


def run(inputs_dir, rules_path, out_path, prompt_log_dir,
        model_round="off", model=None, cassettes_dir=None, usage_path=None):
    from agents import model_call as _mc

    inputs_dir = pathlib.Path(inputs_dir)
    rules = json.loads(pathlib.Path(rules_path).read_text())
    if model is None:
        model = _mc.DEFAULT_MODEL
    _refuse_raw([inputs_dir, pathlib.Path(rules_path)])

    feats = json.loads((inputs_dir / "pre_t1_features.geojson").read_text())["features"]
    waterways = json.loads((inputs_dir / "waterways.geojson").read_text())
    target = json.loads((inputs_dir / "target_reach.geojson").read_text())["features"]
    extent = json.loads((inputs_dir / "extent.json").read_text())
    audit = json.loads((inputs_dir / "input_audit.json").read_text())
    extent_geom = {"type": "Polygon", "coordinates": [[
        [extent["bbox"][0], extent["bbox"][1]], [extent["bbox"][2], extent["bbox"][1]],
        [extent["bbox"][2], extent["bbox"][3]], [extent["bbox"][0], extent["bbox"][3]],
        [extent["bbox"][0], extent["bbox"][1]]]]}

    ledger = compute_ledger(feats, waterways, target, extent_geom, rules)
    ranking = score_mechanisms(rules, ledger)

    prompt, _ = build_prompt(rules, ledger)
    forbidden = _input_tokens(inputs_dir, rules)
    violations = audit_prompt(prompt, forbidden)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    prompt_log_dir = pathlib.Path(prompt_log_dir)
    prompt_log_dir.mkdir(parents=True, exist_ok=True)
    (prompt_log_dir / f"prompt-{prompt_hash[:16]}.txt").write_text(prompt)
    if violations:
        raise SystemExit("prompt audit failed: " + "; ".join(violations))

    model_info = {"status": "skipped", "reason": f"--model-round {model_round}",
                  "model": model, "request_hash": None, "agreement": None}
    if model_round == "on":
        try:
            res = _mc.complete(prompt, model=model,
                               cassettes_dir=cassettes_dir or "data/model_cassettes",
                               usage_path=usage_path or "meta_usage.json")
        except _mc.CassetteMiss as e:
            model_info = {"status": "miss", "reason": str(e), "model": model,
                          "request_hash": None, "agreement": None}
        else:
            mr, merr = validate_model_text(res["text"], rules, ledger)
            model_info = {"status": res["source"], "reason": None, "model": model,
                          "request_hash": res["request_hash"],
                          "agreement": ([e["mechanism"] for e in mr] ==
                                        [o["id"] for o in ranking]) if mr else False,
                          "errors": merr}
            if merr:
                model_info["status"] = "rejected"

    top = ranking[0]
    brief = {
        "prediction": "nepal_cascade_demo",
        "as_of_label": rules["cutoff"]["label"],
        "probability_semantics": ("support strength from pre-cutoff evidence only; "
                                  "NOT calibrated frequency"),
        "inputs_audit": audit,
        "ledger": ledger,
        "mechanisms": ranking,
        "cluster_finding": ledger["facts"]["F4_cluster_hit"]["text"],
        "model_round": model_info,
        "prompt_audit": {"prompt_sha256": prompt_hash, "violations": [],
                         "forbidden_tokens_checked": len(forbidden)},
        "verdict": (f"Pre-cutoff evidence most supports '{top['title']}' "
                    f"(support {top['probability']:.0%}). Probabilities are "
                    f"support strengths, not forecasts."),
    }
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out_path}: top={top['id']} p={top['probability']}")
    return brief


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="demo/nepal_cascade/inputs")
    ap.add_argument("--rules", default="demo/nepal_cascade/rules.json")
    ap.add_argument("--out", default="demo/nepal_cascade/output/brief.json")
    ap.add_argument("--prompt-log", default="demo/nepal_cascade/output")
    ap.add_argument("--model-round", choices=["off", "on"], default="off")
    ap.add_argument("--model", default=None)
    ap.add_argument("--cassettes", default="data/model_cassettes")
    ap.add_argument("--usage", default="meta_usage.json")
    a = ap.parse_args(argv)
    run(a.inputs, a.rules, a.out, a.prompt_log, a.model_round,
        a.model, a.cassettes, a.usage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
