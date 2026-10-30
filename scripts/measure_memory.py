#!/usr/bin/env python3
"""Honest measurement for tiered memory (M2): the null test.

Can the adjust math manufacture skill from noise? Two arms, same frozen
ranking, same trial count, one fixed seed:

- null arm: history labels are coin flips (no signal). Adjusted must NOT
  beat frozen beyond ``max_null_edge``. Expectation: it loses, because
  capped shifts still chase noise.
- signal arm: history labels always back the true winner. Adjusted MUST
  beat frozen by at least ``min_signal_edge`` — the positive control that
  proves this test can detect real help when it exists.

Pure simulation on preregistered parameters; it reads no study data and
claims nothing about either study. Exit 0 when both arms behave, 1 with
the rates printed when either misbehaves.

Usage:
  python scripts/measure_memory.py [--memory-config config/preregistered_memory.yaml]
"""
from __future__ import annotations

import argparse
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.memory import memory_adjust  # noqa: E402

MECHANISMS = ["suppression_then_restart", "sustained_suppression",
              "continued_spread", "fuel_burnout"]
LABELS = ["restart", "quiet"]


def run_arm(signal: bool, seed: int, trials: int, history_len: int,
            frozen_probs: list, supports: dict, mem: dict) -> dict:
    """One arm. Returns frozen/adjusted hit rates and the edge."""
    rng = random.Random(seed)
    inv = {m: lab for lab, ms in supports.items() for m in ms}
    frozen_hits = adjusted_hits = 0
    for _ in range(trials):
        truth = rng.choices(MECHANISMS, weights=frozen_probs)[0]
        if signal:
            labels = [inv.get(truth, LABELS[0])] * history_len
        else:
            labels = [rng.choice(LABELS) for _ in range(history_len)]
        hits = {m: 0 for m in MECHANISMS}
        for lab in labels:
            for m in supports.get(lab, []):
                hits[m] += 1
        stats = {"signature": {"id": "synthetic", "readable": []},
                 "episodes": history_len, "labeled": history_len,
                 "labels": {}, "hits": hits}
        ranking = [{"id": m, "title": m, "probability": p}
                   for m, p in zip(MECHANISMS, frozen_probs)]
        adjusted, _ = memory_adjust(ranking, stats, mem)
        frozen_hits += ranking[0]["id"] == truth
        adjusted_hits += adjusted[0]["id"] == truth
    return {"frozen": frozen_hits / trials, "adjusted": adjusted_hits / trials,
            "edge": (adjusted_hits - frozen_hits) / trials}


def main(argv=None) -> int:
    import yaml
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--memory-config",
                    default=str(ROOT / "config/preregistered_memory.yaml"))
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(pathlib.Path(a.memory_config).read_text())
    nt = cfg["null_test"]
    mem = {"min_episodes_to_speak": 1,  # synthetic histories always speak;
           "smoothing_alpha": cfg["memory"]["smoothing_alpha"],  # ...so the
           "max_abs_shift": cfg["memory"]["max_abs_shift"]}  # arms test math
    supports = cfg["memory"]["outcome_supports"]
    null = run_arm(False, nt["seed"], nt["trials"], nt["history_len"],
                   nt["frozen_probs"], supports, mem)
    sig = run_arm(True, nt["seed"] + 1, nt["trials"], nt["history_len"],
                  nt["frozen_probs"], supports, mem)
    print(f"null arm:   frozen={null['frozen']:.3f} adjusted={null['adjusted']:.3f} "
          f"edge={null['edge']:+.3f} (must be <= {nt['max_null_edge']:+.3f})")
    print(f"signal arm: frozen={sig['frozen']:.3f} adjusted={sig['adjusted']:.3f} "
          f"edge={sig['edge']:+.3f} (must be >= {nt['min_signal_edge']:+.3f})")
    ok = (null["edge"] <= nt["max_null_edge"]
          and sig["edge"] >= nt["min_signal_edge"])
    print("MEASURE:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
