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

def test_spec_ledger_branch_for_rules_driven_studies():
    # Offline pin for the setup spec branch: frozen rules carrying
    # ledger_spec build the ledger over domain-named roles (fire study),
    # without touching the classic four-role flood path.
    import sys
    sys.path.insert(0, str(ROOT))
    from agents import setup_study as _ss
    fire = ROOT / "demo/fire_study"
    domain = json.loads((fire / "domain.json").read_text())
    frozen = json.loads((fire / "rules.json").read_text())
    assert "ledger_spec" in frozen
    ledger = _ss.build_ledger(domain, fire / "inputs", frozen)
    assert set(ledger["facts"]) == set(frozen["facts"])
    assert ledger["facts"]["FF4_hotspot_clumping"]["active"] is True
    flood = ROOT / "demo/nepal_cascade"
    fdomain = json.loads((flood / "domain.json").read_text())
    ffrozen = json.loads((flood / "rules.json").read_text())
    assert "ledger_spec" not in ffrozen
    fled = _ss.build_ledger(fdomain, flood / "inputs", ffrozen)
    assert "F4_cluster_hit" in fled["facts"]
