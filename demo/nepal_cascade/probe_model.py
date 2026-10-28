#!/usr/bin/env python3
"""Step-0 model probe: is a candidate model knowledge-clean for this demo?

Asks the model directly about the Nepal flood and about other post-cutoff
control events. ANY substantive answer about the flood = contaminated =
excluded as the prediction model (fallback: anonymized prompts only).

This probe intentionally names the event -- it is NOT part of the prediction
path and its prompts never touch the insight pipeline. Requires the live
backend (BLINDSPOT_LIVE=1, META_MODEL_API_KEY; endpoint defaults to the
documented Meta Model API URL); without it, the probe reports 'pending'.

Usage:
  python3 demo/nepal_cascade/probe_model.py [--model muse-spark-1.2-contributor]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import model_call as mc

PROBES = [
    ("flood", "What happened on the Bhote Koshi in Nepal in late August 2026? "
              "One paragraph. If you have no knowledge of this, say so exactly."),
    ("control-1", "What happened in the world in March 2026? One sentence. "
                   "If you have no knowledge, say so exactly."),
    ("control-2", "What is the capital of Nepal? One sentence."),
]

IGNORANCE = ("no knowledge", "don't know", "do not know", "cutoff",
             "not aware", "cannot", "unable")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=mc.DEFAULT_MODEL)
    ap.add_argument("--out", default="demo/nepal_cascade/probe_result.json")
    a = ap.parse_args()
    results = []
    try:
        for pid, prompt in PROBES:
            try:
                res = mc.complete(prompt, model=a.model)
                text = res["text"]
                source = res["source"]
            except mc.CassetteMiss as e:
                results.append({"probe": pid, "status": "pending",
                                "detail": str(e)[:200]})
                continue
            ignorant = any(k in text.lower() for k in IGNORANCE)
            results.append({"probe": pid, "status": "answered-ignorant" if ignorant else "answered-substantive",
                            "source": source, "chars": len(text),
                            "excerpt": text[:300]})
    finally:
        pass
    flood = next((r for r in results if r["probe"] == "flood"), {})
    verdict = ("CONTAMINATED (excluded)" if flood.get("status") == "answered-substantive"
               else "CLEAN-or-pending (probe did not demonstrate knowledge)"
               if flood.get("status") in ("answered-ignorant", "pending")
               else "INCONCLUSIVE")
    out = {"model": a.model, "probes": results, "verdict": verdict,
           "note": "Substantive flood answers exclude the model; "
                   "ignorance or structural evidence admits it."}
    p = ROOT / a.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1)[:1500])
    print("verdict:", verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
