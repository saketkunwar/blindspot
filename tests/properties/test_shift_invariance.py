"""Committed joint-shift invariance: rigidly shifting all inputs (flood +1 lon;
FIRMS +1 lon / +0.5 lat / +7 d incl. payload dates; timeline +7 d) must move
fire cells/dates identically while verdicts, relations, and triggers stay
equal, and flood snapshots stay equal up to 1e-6. Fail-closed: any red means
hardcoded coordinates, dates, or counts.
"""
import datetime as dt
import hashlib
import json
import math
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DLON_FLOOD = 1.0
DLON_FIRE, DLAT_FIRE, DD_FIRE = 1.0, 0.5, 7


def _run(mod, data_dir, out):
    r = subprocess.run([sys.executable, "-m", mod, "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(pathlib.Path(out).read_text())


def _shift_coords(o, dlon, dlat):
    if isinstance(o, dict):
        if "coordinates" in o and "type" in o:
            def sh(c):
                if c and isinstance(c[0], (int, float)):
                    return [c[0] + dlon, c[1] + dlat] + list(c[2:])
                return [sh(x) for x in c]
            o["coordinates"] = sh(o["coordinates"])
        for v in o.values():
            if isinstance(v, (dict, list)):
                _shift_coords(v, dlon, dlat)
    elif isinstance(o, list):
        for v in o:
            _shift_coords(v, dlon, dlat)


def _shift_day(s, days):
    return (dt.date.fromisoformat(s[:10]) + dt.timedelta(days=days)).isoformat() + s[10:]


def _shifted_data(tmp_path):
    d = tmp_path / "data"
    shutil.copytree(ROOT / "data", d, ignore=shutil.ignore_patterns("MANIFEST.json"))
    for f in (d / "flood_nepal").glob("*.geojson"):
        o = json.loads(f.read_text())
        _shift_coords(o, DLON_FLOOD, 0.0)
        f.write_text(json.dumps(o))
    for f in (d / "fire_kalimantan").glob("*.json"):
        o = json.loads(f.read_text())
        recs = o.get("detections") if isinstance(o, dict) else o
        if isinstance(recs, list):
            for r in recs:
                pr = r.get("properties", r)
                if "lat" in pr:
                    pr["lat"] = float(pr["lat"]) + DLAT_FIRE
                if "lon" in pr:
                    pr["lon"] = float(pr["lon"]) + DLON_FIRE
                for holder in (r.get("payload"), pr):
                    if isinstance(holder, dict):
                        for k in ("acq_date", "date", "acquisition_date", "valid_time"):
                            if k in holder and DD_FIRE:
                                holder[k] = _shift_day(str(holder[k]), DD_FIRE)
        f.write_text(json.dumps(o))
    t = json.loads((d / "synthetic" / "operator_timeline.json").read_text())
    for p in t["phases"] + [t["claim"]]:
        p["start"] = _shift_day(p["start"], DD_FIRE)[:10]
        p["end"] = _shift_day(p["end"], DD_FIRE)[:10]
    (d / "synthetic" / "operator_timeline.json").write_text(json.dumps(t))
    m = {str(f.relative_to(d)): {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                 "kind": "perturbed", "source_url": "shift test", "license": "n/a"}
         for f in d.rglob("*") if f.is_file() and f.name != "MANIFEST.json"}
    (d / "MANIFEST.json").write_text(json.dumps(m))
    return d


def _close(a, b, rel=1e-6, ab=1e-9):
    return abs(a - b) <= max(ab, rel * max(abs(a), abs(b)))


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("shift")
    mods = {"flood": "pipelines.flood_secondary_dam", "fire": "pipelines.fire_peat_evasion"}
    base = {s: _run(m, "data", tmp / f"b_{s}.json") for s, m in mods.items()}
    shifted = _shifted_data(tmp)
    moved = {s: _run(m, shifted, tmp / f"m_{s}.json") for s, m in mods.items()}
    return base, moved


def test_flood_snapshots_invariant(pair):
    base, moved = pair[0]["flood"], pair[1]["flood"]
    bf = {f["id"]: f for f in base["act1"]["features"]}
    mf = {f["id"]: f for f in moved["act1"]["features"]}
    assert bf.keys() == mf.keys()
    for i in bf:
        for side in ("fwd", "inv"):
            a, b = bf[i][side], mf[i][side]
            assert a["rcc8"] == b["rcc8"] and a["rectangle"] == b["rectangle"]
            assert sorted(a["tiles"]) == sorted(b["tiles"])
            assert a["bearing"] == b["bearing"] and a["band"] == b["band"]
            assert _close(a["edge_gap_m"], b["edge_gap_m"])
            assert _close(a["centroid_dist_km"], b["centroid_dist_km"])
        assert bf[i]["split_alert"] == mf[i]["split_alert"]
    assert base["act3"]["status"] == moved["act3"]["status"]
    assert base["act3"]["detector_a"]["triggered"] == moved["act3"]["detector_a"]["triggered"]


def test_fire_joint_shift_invariant(pair):
    base, moved = pair[0]["fire"], pair[1]["fire"]

    def view(res, dlon, dlat):
        out = {}
        for c in res["cells"]:
            lon, lat = (float(x) for x in c["id"].split(","))
            ds = sorted(c["counts"])
            out[f"{lon + dlon:.1f},{lat + dlat:.1f}"] = (
                [c["counts"][x] for x in ds], [c["rcc8"][x] for x in ds],
                [v["violation"] for v in c["continuity"]])
        return out

    assert view(base, DLON_FIRE, DLAT_FIRE) == view(moved, 0.0, 0.0)
    bd = sorted({d for c in base["cells"] for d in c["counts"]})
    md = sorted({d for c in moved["cells"] for d in c["counts"]})
    assert [_shift_day(x, DD_FIRE)[:10] for x in bd] == md
    assert [x["verdict"] for x in base["claims"]] == [x["verdict"] for x in moved["claims"]]
    assert [x["relation"] for x in base["timeline_relations"]] == [x["relation"] for x in moved["timeline_relations"]]
    assert base["detector_b"]["triggered"] == moved["detector_b"]["triggered"]
