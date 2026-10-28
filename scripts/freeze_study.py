#!/usr/bin/env python3
"""Freeze a setup draft into a study's frozen rules (Step 5).

Copy, never in-place edit: reads a setup report (draft + hashes), rebuilds
the draft's ranking on the real ledger for the record, and writes a new
``rules.json`` plus a ``freeze.json`` pin file recording the card, prompt,
draft, and inputs-audit hashes. Prints the ``git tag study/<domain>/v1``
command for human approval -- tagging itself stays a human act.

Usage:
  python3 scripts/freeze_study.py --report demo/nepal_cascade/output/setup-report-<hash>.json
      --domain demo/nepal_cascade/domain.json --inputs demo/nepal_cascade/inputs
      --out-rules /tmp/rules.draft.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import setup_study as su


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out-rules", required=True)
    ap.add_argument("--out-freeze", default=None)
    a = ap.parse_args(argv)

    report = json.loads(pathlib.Path(a.report).read_text())
    draft, errors = su.validate_draft(
        json.dumps(report.get("draft")), set(report.get("draft", {})
                                             .get("weights", {})))
    if errors or draft is None:
        print("refusing to freeze an invalid draft:")
        for e in errors:
            print(f"  - {e}")
        return 1
    ok, top = su.null_test(draft)
    if not ok:
        print(f"refusing to freeze: null red-team fails (top={top})")
        return 1

    domain = json.loads(pathlib.Path(a.domain).read_text())
    ledger = su.build_ledger(domain, pathlib.Path(a.inputs))
    rules_like = {"mechanisms": draft["mechanisms"],
                  "facts": {fid: {"weight": w}
                            for fid, w in draft["weights"].items()}}
    from engine.ledger import score_mechanisms

    ranking = score_mechanisms(rules_like, ledger)
    rules = {"mechanisms": draft["mechanisms"],
             "facts": {fid: {"weight": w, "description": ""}
                       for fid, w in draft["weights"].items()},
             "caution_prior": {"mechanism": "no_further_event", "weight": 0.5,
                               "rationale": ("Absence of post-cutoff evidence "
                                             "favors restraint.")},
             "cluster_rule": draft.get("cluster_rule", {}),
             "cutoff": {"label": "pre-T1",
                        "rule": (domain.get("cutoff") or {}).get("rule", "")},
             "activation": {fid: "active per compute round" for fid in draft["weights"]},
             "meta": {"frozen": "fill in date + commit + tag on approval",
                      "source_report": pathlib.Path(a.report).name}}
    out_rules = pathlib.Path(a.out_rules)
    out_rules.write_text(json.dumps(rules, indent=1, sort_keys=True) + "\n")
    freeze = {
        "rules_sha256": hashlib.sha256(out_rules.read_bytes()).hexdigest(),
        "report": pathlib.Path(a.report).name,
        "prompt_sha256": report.get("prompt_sha256"),
        "request_hash": report.get("request_hash"),
        "draft_top_on_real_ledger": ranking[0]["id"],
        "null_test": {"pass": ok, "top": top},
    }
    out_freeze = pathlib.Path(a.out_freeze or str(out_rules) + ".freeze.json")
    out_freeze.write_text(json.dumps(freeze, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out_rules} + {out_freeze.name}")
    print(f"human approval still required: git tag study/{domain.get('domain_id')}/v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
