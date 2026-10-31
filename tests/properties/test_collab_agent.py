"""Durable tests for the morning-brief agent (collab_agent/).

Offline only: the October 30 committed pull is the fixture (no key, no
network). Tree writes are forbidden here — every run targets tmp_path.
"""
import csv
import json

import yaml

from collab_agent import brief as _brief
from collab_agent import decide as _decide
from collab_agent import morning as _morning


def _cfg():
    import yaml as _y
    return _y.safe_load(open("collab_agent/config.yaml"))


def _run_fixture(tmp, name="a"):
    out = tmp / name
    rc = _morning.main(["--fixture", "oct30", "--out-dir", str(out),
                        "--no-snapshot"])
    assert rc == 0
    return out


def test_fixture_deterministic(tmp_path):
    a = _run_fixture(tmp_path, "a")
    b = _run_fixture(tmp_path, "b")
    assert (a / "digest.json").read_bytes() == (b / "digest.json").read_bytes()
    assert (a / "pull_2026-10-30.json").read_bytes() == \
        (b / "pull_2026-10-30.json").read_bytes()


def test_fixture_trigger_is_spike_with_audit(tmp_path):
    out = _run_fixture(tmp_path)
    rec = json.loads((out / "digest.json").read_text())[-1]
    assert rec["trigger"] == "spike"
    assert "trailing median" in rec["reason"]
    assert rec["matches_frozen"] is True
    assert rec["snippet"].startswith("2026-10-30: 150 detections")


def _quiet_csv(path):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["acq_date", "longitude",
                                           "latitude"])
        w.writeheader()
        for i, (d, n) in enumerate([("2026-10-26", 2), ("2026-10-27", 1),
                                    ("2026-10-28", 2), ("2026-10-29", 1),
                                    ("2026-10-30", 2)]):
            for j in range(n):
                w.writerow({"acq_date": d,
                            "longitude": 113.0 + i * 0.01 + j * 0.001,
                            "latitude": -1.5 - j * 0.001})


def test_novel_quiet_opens_study(tmp_path):
    # Eight scattered synthetic detections form a signature the archive
    # has never seen, so the honest outcome is new_shape (one study),
    # not quiet — priority the preregistered order pins.
    pull = tmp_path / "quiet.csv"
    _quiet_csv(pull)
    out = tmp_path / "q"
    rc = _morning.main(["--pull", str(pull), "--out-dir", str(out),
                        "--no-snapshot"])
    assert rc == 0
    recs = json.loads((out / "digest.json").read_text())
    assert len(recs) == 1
    rec = recs[0]
    assert rec["trigger"] == "new_shape"
    assert "new shape" in rec["snippet"]


def test_snippet_numbers_must_live_in_block():
    ctx = {"date": "2026-10-30", "count": 150, "median": 18.5,
           "top_id": "suppression_then_restart", "top_prob": 0.8425,
           "match": {"episodes": 6, "labelled": 4}, "speak_bar": 5}
    snippet, block = _brief.render("spike", ctx)
    assert _brief.validate(snippet, block) == []
    bad = dict(block)
    del bad["detections"]
    assert _brief.validate(snippet, bad) != []


def test_trigger_priority():
    cfg = _cfg()["triggers"]
    full = {"triggers": cfg}
    known4 = {"known": True, "episodes": 6, "labelled": 4}
    known5 = {"known": True, "episodes": 7, "labelled": 5}
    unknown = {"known": False, "episodes": 0, "labelled": 0}
    # speak beats everything
    assert _decide.evaluate(("d", 500), [1, 1, 1, 1], known5, None,
                            full)[0] == "speak"
    # new shape beats a spike
    assert _decide.evaluate(("d", 500), [1, 1, 1, 1], unknown, None,
                            full)[0] == "new_shape"
    # spike beats quiet
    assert _decide.evaluate(("d", 500), [1, 1, 1, 1], known4, None,
                            full)[0] == "spike"
    # quiet after a matched day
    prev = {"matched_pattern": True}
    assert _decide.evaluate(("d", 2), [100, 100, 100, 100], known4, prev,
                            full)[0] == "quiet_after_match"
    # plain quiet
    assert _decide.evaluate(("d", 2), [100, 100, 100, 100], known4, None,
                            full)[0] is None


def test_live_without_key_skips_cleanly(tmp_path, monkeypatch):
    for name in ("FIRMS_MAP_KEY", "NASA_FIRMS_MAP_KEY"):
        monkeypatch.delenv(name, raising=False)
    rc = _morning.main(["--live", "--out-dir", str(tmp_path / "o"),
                        "--no-snapshot"])
    assert rc == 0
    assert not (tmp_path / "o" / "digest.json").exists()
