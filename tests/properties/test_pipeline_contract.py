"""Durable pipeline contract + invariance. FAILS (not skips) until pipelines exist — fail-closed by design.
Covers: CLI contract, fwd/inv inverse consistency, cell/date coverage, shift invariance, order invariance."""
import json, pathlib, shutil, subprocess, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
INV = {"DC": "DC", "EC": "EC", "PO": "PO", "EQ": "EQ", "TPP": "TPPi", "NTPP": "NTPPi", "TPPi": "TPP", "NTPPi": "NTPP"}

def run(mod, data_dir, out):
    r = subprocess.run([sys.executable, "-m", mod, "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(pathlib.Path(out).read_text())

@pytest.fixture(scope="module")
def results(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pipes")
    return {"flood": run("pipelines.flood_secondary_dam", "data", tmp / "flood.json"),
            "fire": run("pipelines.fire_peat_evasion", "data", tmp / "fire.json")}

def test_flood_inverse_and_missing_input(results):
    for f in results["flood"]["act1"]["features"]:
        assert INV[f["fwd"]["rcc8"]["relation"]] == f["inv"]["rcc8"]["relation"]
        assert f["fwd"]["edge_gap_m"] >= 0
    a3 = results["flood"]["act3"]
    assert a3["status"] in ("ok", "missing_input")
    if a3["status"] == "missing_input": assert a3["impoundment_vs_union"] is None and a3["missing"]

def test_fire_cells_cover_dates(results):
    dates = set(results["fire"]["dates"])
    assert results["fire"]["cells"]
    for c in results["fire"]["cells"]:
        assert set(c["counts"]) == dates and set(c["rcc8"]) == dates
        lon, lat = c["id"].split(",")
        assert c["origin"] == [float(lon), float(lat)]

def test_fire_shift_invariance(tmp_path):
    base = run("pipelines.fire_peat_evasion", "data", tmp_path / "b.json")
    d = tmp_path / "data"; shutil.copytree(ROOT / "data", d, ignore=shutil.ignore_patterns("MANIFEST.json"))
    # shift every FIRMS detection +0.5 lat and timeline +30d via layout-aware rewrite
    for p in (d / "fire_kalimantan").glob("*.json"):
        obj = json.loads(p.read_text())
        recs = obj.get("detections") if isinstance(obj, dict) else obj
        if isinstance(recs, list):
            for r in recs:
                if "lat" in r: r["lat"] += 0.5
                if "latitude" in r: r["latitude"] += 0.5
        p.write_text(json.dumps(obj))
    import hashlib
    m = {str(f.relative_to(d)): {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
         "kind": "perturbed", "source_url": "perturbed copy", "license": "n/a"}
         for f in d.rglob("*") if f.is_file() and f.name != "MANIFEST.json"}
    (d / "MANIFEST.json").write_text(json.dumps(m))
    moved = run("pipelines.fire_peat_evasion", d, tmp_path / "m.json")
    def view(res, dlat=0.0):
        return {f"{float(c['id'].split(',')[0]):.1f},{float(c['id'].split(',')[1])+dlat:.1f}":
                [c["counts"][x] for x in sorted(c["counts"])] for c in res["cells"]}
    assert view(base, 0.5) == view(moved)
