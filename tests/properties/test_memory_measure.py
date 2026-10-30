"""M2 honest measurement: the null/signal arms behave as preregistered.

Small deterministic checks on the measurement arms (the full 200-trial run
is G21's job): arms return valid rates, the null arm on noise does not beat
frozen here, the signal arm on perfect information does, and the margins in
config decide the verdict.
"""
import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import measure_memory as mm  # noqa: E402

CFG = yaml.safe_load((ROOT / "config/preregistered_memory.yaml").read_text())
NT = CFG["null_test"]
MEM = {"min_episodes_to_speak": 1,
       "smoothing_alpha": CFG["memory"]["smoothing_alpha"],
       "max_abs_shift": CFG["memory"]["max_abs_shift"]}
SUPPORTS = CFG["memory"]["outcome_supports"]
MECHS = mm.MECHANISMS


def _arm(signal):
    return mm.run_arm(signal, NT["seed"], 40, NT["history_len"],
                      NT["frozen_probs"], SUPPORTS, MEM)


def test_arms_return_valid_rates():
    for signal in (False, True):
        r = _arm(signal)
        assert 0.0 <= r["frozen"] <= 1.0
        assert 0.0 <= r["adjusted"] <= 1.0
        assert r["edge"] == pytest.approx(r["adjusted"] - r["frozen"])


def test_null_does_not_win_signal_does():
    null = _arm(False)
    sig = _arm(True)
    assert null["edge"] <= NT["max_null_edge"]
    assert sig["edge"] >= NT["min_signal_edge"]


def test_arms_are_deterministic():
    assert _arm(False) == _arm(False)
    assert _arm(True) == _arm(True)


def test_measure_script_reports_both_arms():
    import subprocess
    r = subprocess.run([sys.executable, "scripts/measure_memory.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0
    assert "null arm:" in r.stdout and "signal arm:" in r.stdout
    assert "MEASURE: OK" in r.stdout
