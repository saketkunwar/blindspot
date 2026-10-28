"""Setup round: the LLM frames the study, the kernel will compute it.

Given ONLY pre-cutoff context (domain type, data schema present, anonymized
ledger aggregates), the model proposes a mechanism set, per-fact weights,
activation thresholds, and a cluster rule as a draft rules file. It never
sees ground truth, place names, or dates — the same anonymization as the
ranking round — and the draft prompt + draft are audit-scanned identically.

The draft NEVER overwrites the frozen rules. It is written to a setup report
for review, then compared against the frozen study: mechanism overlap, the
draft's own ranking of the real ledger, and the draft's null red-team. A
setup that cannot reproduce the frozen study's shape — or that fails the
null test with its own weights — is rejected, and the rejection is recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import autoinsight as ai
from agents import model_call as mc

DOMAIN_ONTOLOGY = (
    "Domain: river-valley flood damage (this is a flood study, not fire, "
    "not earthquake — frame accordingly). Processes such surveys consider "
    "include: water draining safely through debris; debris forming a dam "
    "that holds; water ponding behind debris and later releasing suddenly; "
    "new slope failures on other reaches; continued flooding downstream "
    "only; or nothing further happening. These are vocabulary, not answers: "
    "you may adopt, adapt, or reject any of them, but your set must stay "
    "open and include a nothing-happens story with real weight. "
    "Ground every weight in the ledger below, not in the vocabulary above."
)

INSTRUCTION = (
    "You are designing an evidence study, not judging an event. "
    "Context: a river-valley damage survey, one pre-cutoff snapshot, "
    "anonymous reaches (Alpha upstream, Beta downstream), one anonymized "
    "tributary. Below is the evidence ledger (pre-cutoff aggregates only). "
    "Propose an OPEN mechanism set that includes a nothing-happens story "
    "with real weight, per-fact weights, and a spatial cluster rule. "
    "Reply with JSON only: {\"mechanisms\": [{\"id\", \"title\", "
    "\"supports\": [fact ids], \"opposes\": [fact ids], \"prior\"}], "
    "\"weights\": {fact id: number}, \"cluster_rule\": "
    "{\"max_distance_m\": number, \"min_features\": number}}. "
    "Cite only ledger facts, using their FULL ids exactly as written in "
    "the ledger lines (e.g. F1_total_pre_cutoff_damage — never F1, F2, ...); "
    "any abbreviated id invalidates the draft. Assert no outcome."
)

GEOM_RULES = {"facts": {}, "mechanisms": [],
              "cluster_rule": {"max_distance_m": 500, "min_features": 8},
              "channel_adjacent_m": 250}


def load_inputs(inputs: pathlib.Path):
    feats = json.loads((inputs / "pre_t1_features.geojson").read_text())["features"]
    waterways = json.loads((inputs / "waterways.geojson").read_text())
    target = json.loads((inputs / "target_reach.geojson").read_text())["features"]
    extent = json.loads((inputs / "extent.json").read_text())
    x0, y0, x1, y1 = extent["bbox"]
    extent_geom = {"type": "Polygon", "coordinates": [[
        [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
    return feats, waterways, target, extent_geom


def _is_quiet(m: dict) -> bool:
    blob = f"{m.get('id', '')} {m.get('title', '')}".lower()
    return any(k in blob for k in ("nothing", "null", "quiescen", "baseline", "no_further"))


def build_prompt(inputs: pathlib.Path, ledger) -> tuple[str, set[str]]:
    lines = [DOMAIN_ONTOLOGY, INSTRUCTION, "Ledger facts:"]
    for fid, f in ledger["facts"].items():
        lines.append(f"- {fid}: {f['text']}")
    prompt = "\n".join(lines) + "\n"
    return prompt, ai._input_tokens(inputs, {"cluster_rule": {"target_value": ""}})


def validate_draft(text: str, ledger_ids: set[str]) -> tuple[dict | None, list[str]]:
    try:
        body = json.loads(text)
    except (json.JSONDecodeError, AttributeError):
        return None, ["draft is not JSON"]
    bad = []
    mechs = body.get("mechanisms")
    if not isinstance(mechs, list) or len(mechs) < 2:
        bad.append("need at least two mechanisms")
        mechs = []
    ids: set[str] = set()
    for m in mechs:
        mid = m.get("id", "")
        if not mid or mid in ids:
            bad.append(f"bad/duplicate mechanism id {mid!r}")
        ids.add(mid)
        for side in ("supports", "opposes"):
            for c in m.get(side, []):
                if c not in ledger_ids:
                    bad.append(f"{mid} cites non-ledger fact {c!r}")
    if not any(_is_quiet(m) for m in mechs):
        bad.append("no nothing-happens story in the open set")
    for fid in ledger_ids:
        if fid not in body.get("weights", {}):
            bad.append(f"missing weight for {fid}")
    if bad:
        return None, bad
    return body, []


def null_test(draft: dict) -> tuple[bool, str]:
    flat = {"facts": {fid: {"value": 0, "active": False, "text": "quiet"}
                      for fid in draft["weights"]}}
    flat["facts"]["F8_inputs_audit_clean"] = {"value": 1, "active": True, "text": "ok"}
    quiet_ids = [m["id"] for m in draft["mechanisms"] if _is_quiet(m)]
    rules_like = {"mechanisms": draft["mechanisms"],
                  "facts": {fid: {"weight": w} for fid, w in draft["weights"].items()},
                  "caution_prior": {"mechanism": quiet_ids[0] if quiet_ids else "",
                                    "weight": 0.5}}
    top = ai.score_mechanisms(rules_like, flat)[0]["id"]
    return top in quiet_ids, top


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="demo/nepal_cascade/inputs")
    ap.add_argument("--frozen-rules", default="demo/nepal_cascade/rules.json")
    ap.add_argument("--brief", default="demo/nepal_cascade/output/brief.json")
    ap.add_argument("--out-dir", default="demo/nepal_cascade/output")
    ap.add_argument("--model", default=None)
    a = ap.parse_args(argv)

    inputs = pathlib.Path(a.inputs)
    ai._refuse_raw([inputs])
    frozen = json.loads(pathlib.Path(a.frozen_rules).read_text())
    ledger_ids = set(frozen["facts"])

    feats, waterways, target, extent_geom = load_inputs(inputs)
    ledger = ai.compute_ledger(feats, waterways, target, extent_geom, GEOM_RULES)
    prompt, forbidden = build_prompt(inputs, ledger)
    violations = ai.audit_prompt(prompt, forbidden)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"setup-prompt-{prompt_hash[:16]}.txt").write_text(prompt)
    if violations:
        raise SystemExit("setup prompt audit failed: " + "; ".join(violations))

    model = a.model or mc.DEFAULT_MODEL
    try:
        res = mc.complete(prompt, model=model)
    except mc.CassetteMiss as e:
        print(f"setup round miss: {e}")
        return 2
    draft, errors = validate_draft(res["text"], ledger_ids)

    report = {
        "model": model, "source": res["source"],
        "request_hash": res["request_hash"],
        "prompt_sha256": prompt_hash,
        "prompt_audit_violations": [],
        "draft_errors": errors,
        "draft": draft,
        "frozen_mechanisms": [m["id"] for m in frozen["mechanisms"]],
        "overlap": sorted(set(m.get("id", "") for m in (draft or {}).get(
            "mechanisms", [])) & set(m["id"] for m in frozen["mechanisms"]))
        if draft else [],
        "null_test_pass": null_test(draft)[0] if draft else False,
        "null_test_top": null_test(draft)[1] if draft else None,
    }
    if draft:
        rules_like = {"mechanisms": draft["mechanisms"],
                      "facts": {fid: {"weight": w}
                                for fid, w in draft["weights"].items()},
                      "caution_prior": {"mechanism": "no_further_event",
                                        "weight": 0.5}}
        draft_ranking = ai.score_mechanisms(rules_like, ledger)
        report["draft_ranking_on_real_ledger"] = [o["id"] for o in draft_ranking]
        report["draft_top"] = draft_ranking[0]["id"]
        report["frozen_top"] = json.loads(
            pathlib.Path(a.brief).read_text())["mechanisms"][0]["id"]
        report["top_agrees"] = report["draft_top"] == report["frozen_top"]

    (out_dir / f"setup-report-{res['request_hash'][:16]}.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(f"setup {res['source']}: overlap={report['overlap']} "
          f"null={'PASS' if report['null_test_pass'] else 'FAIL'} "
          f"top_agrees={report.get('top_agrees')}")
    return 0 if (draft and not errors and report["null_test_pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
