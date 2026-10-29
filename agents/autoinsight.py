"""Autoinsight: hindsight-free mechanism ranking over pre-cutoff inputs.

Thin CLI over :mod:`engine.ledger`. Prediction path. Reads ONLY the curated
inputs directory, the frozen rules file, and geometry kernels. It refuses to
open anything under ``data/raw`` (the ground-truth side) by construction:
every resolved input path is checked, and a path inside ``data/raw`` fails
the run.

Loop: kernel pass (per-feature RCC-8 vs the static outline, reach split,
continuity aggregates) -> ledger of evidence facts -> rival framing from the
frozen mechanism set -> optional model round with a fully anonymized prompt
-> verification gate (only ledger-grounded claims survive) -> brief with
support-strength probabilities (softmax over documented scores; explicitly
NOT calibrated frequencies).

The model prompt carries no place names, no calendar dates, and no outcome
assertions: anonymous areas, relative snapshot labels, mechanisms listed
only as candidate hypotheses. The exact prompt is saved verbatim and scanned
against tokens drawn from the inputs themselves (any name or date the inputs
contain is forbidden in the prompt), so anonymization is checked, not
promised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import fhz as _fhz
from engine.ledger import (
    _close,
    _input_tokens,
    _refuse_raw,
    _resolve_geometry,
    audit_prompt,
    build_prompt,
    compute_ledger,
    compute_ledger_from_spec,
    build_prompt_from_spec,
    load_domain_geometry,
    network_reach_report,
    score_mechanisms,
    validate_model_text,
)

__all__ = [
    "_close",
    "_input_tokens",
    "_refuse_raw",
    "audit_prompt",
    "build_prompt",
    "compute_ledger",
    "load_domain_geometry",
    "score_mechanisms",
    "validate_model_text",
    "run",
    "main",
]


def run(inputs_dir, rules_path, out_path, prompt_log_dir,
        model_round="off", model=None, cassettes_dir=None, usage_path=None,
        domain_path=None, reach_audit_path=None):
    from agents import model_call as _mc

    inputs_dir = pathlib.Path(inputs_dir)
    rules = json.loads(pathlib.Path(rules_path).read_text())
    if model is None:
        model = _mc.DEFAULT_MODEL
    _refuse_raw([inputs_dir, pathlib.Path(rules_path)])

    if domain_path is None:
        domain_path = ROOT / "demo" / "nepal_cascade" / "domain.json"
    domain = json.loads(pathlib.Path(domain_path).read_text())

    audit = json.loads((inputs_dir / "input_audit.json").read_text())
    if "ledger_spec" in rules:
        from engine import facts as _facts

        roles = _facts.load_inputs_by_role(domain, inputs_dir)
        ledger = compute_ledger_from_spec(rules, roles)
        story_problems = _fhz.validate_stories(rules, set(ledger["facts"]))
        if story_problems:
            raise SystemExit("story polarity failed: " + "; ".join(story_problems))
        ranking = score_mechanisms(rules, ledger)
        prompt, _ = build_prompt_from_spec(rules, ledger, domain)
        spec_mode = True
    else:
        feats = json.loads((inputs_dir / "pre_t1_features.geojson").read_text())["features"]
        waterways = json.loads((inputs_dir / "waterways.geojson").read_text())
        target = json.loads((inputs_dir / "target_reach.geojson").read_text())["features"]
        extent = json.loads((inputs_dir / "extent.json").read_text())
        extent_geom = {"type": "Polygon", "coordinates": [[
            [extent["bbox"][0], extent["bbox"][1]], [extent["bbox"][2], extent["bbox"][1]],
            [extent["bbox"][2], extent["bbox"][3]], [extent["bbox"][0], extent["bbox"][3]],
            [extent["bbox"][0], extent["bbox"][1]]]]}

        ledger = compute_ledger(feats, waterways, target, extent_geom, rules,
                                domain=domain)
        story_problems = _fhz.validate_stories(rules, set(ledger["facts"]))
        if story_problems:
            raise SystemExit("story polarity failed: " + "; ".join(story_problems))
        ranking = score_mechanisms(rules, ledger)
        prompt, _ = build_prompt(rules, ledger)
        spec_mode = False
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
        "cluster_finding": ledger["facts"][rules.get("prompt_contract", {}).get(
            "cluster_fact", "F4_cluster_hit")]["text"],
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
    from shapely.geometry import shape as _shape
    from engine import facts as _facts
    reach = None
    if not spec_mode and domain.get("reach_audit"):
        adj_m, _, _ = _resolve_geometry(rules, domain)
        split_lat = _facts._project(_shape(extent_geom)).centroid.y
        reach = network_reach_report(feats, waterways, target, extent_geom,
                                     split_lat, adj_m)
    if reach is not None:
        reach_path = (pathlib.Path(reach_audit_path) if reach_audit_path
                      else out_path.parent / "reach_audit.json")
        reach_path.write_text(json.dumps(reach, indent=1, sort_keys=True) + "\n")
        print(f"wrote {reach_path}: scopes={reach['scopes']}")
    return brief


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="demo/nepal_cascade/inputs")
    ap.add_argument("--rules", default="demo/nepal_cascade/rules.json")
    ap.add_argument("--out", default="demo/nepal_cascade/output/brief.json")
    ap.add_argument("--prompt-log", default="demo/nepal_cascade/output")
    ap.add_argument("--domain", default="demo/nepal_cascade/domain.json")
    ap.add_argument("--model-round", choices=["off", "on"], default="off")
    ap.add_argument("--model", default=None)
    ap.add_argument("--cassettes", default="data/model_cassettes")
    ap.add_argument("--usage", default="meta_usage.json")
    ap.add_argument("--reach-audit-out", default=None)
    a = ap.parse_args(argv)
    run(a.inputs, a.rules, a.out, a.prompt_log, a.model_round,
        a.model, a.cassettes, a.usage, a.domain, a.reach_audit_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
