"""Durable setup invariants — must pass before build starts and stay green. Smallest focused set."""
import hashlib, json, pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_config_complete_and_frozen_ranges():
    cfg = yaml.safe_load((ROOT / "config/preregistered.yaml").read_text())
    def nulls(o):
        return [1 for v in o.values() if v is None or (isinstance(v, dict) and nulls(v))] if isinstance(o, dict) else []
    assert not nulls(cfg)
    assert cfg["fire"]["footprint_buffer_m"] == 187.5
    assert cfg["fire"]["evasion_ha_per_cell"] < cfg["fire"]["evasion_ha_total"] + 1  # D-4 neighbourhood
    assert cfg["flood"]["v_max_m_per_hr"] > 0 and cfg["tolerance"]["ingest_deg"] == 0

def test_manifest_matches_data():
    m = json.loads((ROOT / "data/MANIFEST.json").read_text())
    for rel, e in m.items():
        p = ROOT / "data" / rel
        assert p.exists(), rel
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"], rel
        assert e["kind"] in ("real", "synthetic", "perturbed")
        if e["kind"] == "real": assert "FILL" not in e["source_url"]

def test_firms_scenario_layout():
    for p in (ROOT / "data/fire_kalimantan").glob("*.json"):
        d = json.loads(p.read_text())
        if isinstance(d, dict) and d.get("tag") == "kalimantan_c":
            assert d["bbox"] and d["detections"]
            assert all("lat" in x and "lon" in x and "acq_date" in x["payload"] for x in d["detections"][:50])
            return
    raise AssertionError("kalimantan_c FIRMS file not found")

def test_flood_files_and_timeline():
    for f in ("flood_extent", "bridges", "hydropowers", "helipads", "waterways"):
        assert json.loads((ROOT / f"data/flood_nepal/{f}.geojson").read_text())["features"]
    t = json.loads((ROOT / "data/synthetic/operator_timeline.json").read_text())
    assert all(iv["start"] < iv["end"] for iv in t["phases"] + [t["claim"]])
    # endpoint rule fixture: mobilization ends where clearing starts -> MEETS, never BEFORE
    assert t["phases"][0]["end"] == t["phases"][1]["start"]
