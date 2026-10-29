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

def test_manifest_record_cycle_without_hand_edits(tmp_path):
    # P2 discipline pin: a full register-then-verify cycle through the
    # tool only (no JSON hand edits), including the refusal paths.
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts import check_manifest as _cm
    d = tmp_path / "data"
    d.mkdir()
    (d / "a.json").write_text('{"v": 1}')
    (d / "MANIFEST.json").write_text("{}\n")
    assert "unlisted file: a.json" in _cm.check(d)
    rc = _cm.main(["--data-dir", str(d), "--record", "a.json", "--kind", "bogus"])
    assert rc == 2, "CLI must reject a bad kind"
    out = _cm.record(d, "a.json", "synthetic", "recorded test fixture", "project synthetic")
    assert "recorded a.json" in out
    assert _cm.check(d) == []
    try:
        _cm.record(d, "a.json", "synthetic", "x", "y")
        raise AssertionError("overwrite accepted")
    except SystemExit as e:
        assert "already listed" in str(e)
    try:
        _cm.record(d, "missing.json", "real", "", "")
        raise AssertionError("missing file accepted")
    except SystemExit:
        pass
    try:
        (d / "r.json").write_text("{}")
        _cm.record(d, "r.json", "real", "", "")
        raise AssertionError("sourceless real file accepted")
    except SystemExit as e:
        assert "source_url" in str(e)

def test_ingest_watch_both_directions(tmp_path):
    # P2 G18 pin: unregistered paths fail, stale entries fail, covered
    # trees pass, absent raw dir is vacuously green.
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts import validate_hardened as _vh
    raw = tmp_path / "raw"
    bad, _ = _vh._g18_check(raw)
    assert bad == []
    raw.mkdir()
    (raw / "new_export").mkdir()
    (raw / "new_export" / "a.geojson").write_text("{}")
    bad, detail = _vh._g18_check(raw)
    assert any("REGISTRY.json unreadable" in b for b in bad), detail
    (raw / "REGISTRY.json").write_text('{"version": 1, "entries": {}}')
    bad, detail = _vh._g18_check(raw)
    assert any("unregistered raw path" in b for b in bad), detail
    (raw / "REGISTRY.json").write_text(
        '{"version": 1, "entries": {"new_export": {"source_url": "s", "license": "l"},'
        ' "ghost": {"source_url": "s", "license": "l"}}}')
    bad, _ = _vh._g18_check(raw)
    assert any("stale registry entry" in b for b in bad), bad
    (raw / "REGISTRY.json").write_text(
        '{"version": 1, "entries": {"new_export": {"source_url": "s", "license": "l"}}}')
    bad, detail = _vh._g18_check(raw)
    assert bad == [], detail
    (raw / "REGISTRY.json").write_text(
        '{"version": 1, "entries": {"new_export": {"source_url": "FILL", "license": "l"}}}')
    bad, _ = _vh._g18_check(raw)
    assert any("placeholder" in b for b in bad), bad

def test_setup_with_card_clears_prompt_audit():
    # P5 card-audit fix pin: prompts embedding the card inventory must
    # pass the setup leak boundary (names + dates), offline, both studies.
    import sys
    sys.path.insert(0, str(ROOT))
    from agents import setup_study as _ss
    from engine.ledger import audit_prompt
    for demo in ("demo/nepal_cascade", "demo/fire_study"):
        demo_p = ROOT / demo
        domain = __import__("json").loads((demo_p / "domain.json").read_text())
        fr = __import__("json").loads((demo_p / "rules.json").read_text())
        ledger = _ss.build_ledger(domain, demo_p / "inputs", fr)
        from agents import context_card as _cc
        card = _cc.build_card(domain, demo_p / "inputs")
        prompt, forbidden = _ss.build_prompt(domain, demo_p / "inputs", ledger, card)
        assert "Study context (redacted inventory):" in prompt
        assert audit_prompt(prompt, forbidden) == []
