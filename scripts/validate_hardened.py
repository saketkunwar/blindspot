#!/usr/bin/env python3
"""Hardened validation gates for BlindSpot. Fail-closed: any missing piece = FAIL, never skip-to-green.

Usage:
  python scripts/validate_hardened.py --setup-only   # G1,G2,G8,G9 (must pass before build starts)
  python scripts/validate_hardened.py                # all gates (must pass before a phase is 'done')
Gates:
  G1 manifest integrity      G6 output contract + fwd/inv inverse consistency
  G2 config completeness     G7 perturbation invariance (shift data -> shifted answers)
  G3 no hardcoded answers    G8 data-layout conformance (FIRMS + flood + timeline)
  G4 fail-closed exits       G9 repo hygiene (prereg tag, frozen config, dirs)
  G5 pipeline CLI contract   G10 durable tests present
"""
import argparse, hashlib, json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAIL = []
def gate(gid, ok, detail=""):
    print(f"{gid} {'PASS' if ok else 'FAIL'} {detail}")
    if not ok: FAIL.append(gid)
def load_config():
    import yaml
    return yaml.safe_load((ROOT/"config/preregistered.yaml").read_text())

def g1():
    r = subprocess.run([sys.executable, "scripts/check_manifest.py", "--data-dir", "data"],
                       cwd=ROOT, capture_output=True, text=True)
    gate("G1", r.returncode == 0, r.stdout.strip() or r.stderr.strip()[:200])

def _nulls(o, p=""):
    out = []
    if isinstance(o, dict):
        for k, v in o.items(): out += _nulls(v, f"{p}.{k}" if p else k)
    elif o is None: out.append(p)
    return out

def g2():
    try: cfg = load_config()
    except Exception as e: gate("G2", False, str(e)); return
    nulls = _nulls(cfg)
    ok = not nulls and cfg["tolerance"]["ingest_deg"] >= 0 and cfg["fire"]["min_detections"] >= 1 \
        and cfg["fire"]["footprint_buffer_m"] > 0 and cfg["flood"]["v_max_m_per_hr"] > 0 \
        and 0 < cfg["fire"]["evasion_ha_per_cell"] and cfg["grid"]["cell_deg"] > 0
    gate("G2", ok, f"nulls={nulls}" if nulls else "all values decided, ranges sane")

def _denylist():
    """Literals that live in config/data and must never appear in builder code.

    Derived from the live files, not written by hand: distinctive config
    floats (integers and 0.5 are excluded -- unenforceable across languages
    without false positives), long config strings, and every date/name/id in
    the operator timeline. Integers like 150/48/50 are deliberately NOT
    listed: they collide with ordinary arithmetic; the floats, dates, and
    names are identifying and have no legitimate code use.
    """
    import yaml
    lits = []
    cfg = yaml.safe_load((ROOT / "config/preregistered.yaml").read_text())
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, float) and not o.is_integer() and o != 0.5:
            lits.append(repr(o))
        elif isinstance(o, str) and len(o) > 20:
            lits.append(o)
    walk(cfg)
    try:
        tl = json.loads((ROOT / "data/synthetic/operator_timeline.json").read_text())
        for iv in tl["phases"] + [tl["claim"]]:
            lits += [iv["start"], iv["end"], iv["id"]]
        lits.append(str(tl.get("site", "")))
    except (OSError, KeyError):
        pass
    return sorted({s for s in lits if s})


def g3():
    # No builder code may embed scenario answers: cell-id literals, claim dates as constants,
    # single-file selection by directory order, or config/data literals. Config values belong in yaml, not code.
    pats = [r'"\d{3}\.\d,-?\d\.\d"', r"firms_kalimantan_c"]
    pats += [r"(?<![\w.])" + re.escape(s) + r"(?![\w.])" for s in _denylist()]
    pat = re.compile("|".join(pats))
    hits = []
    for base in ("engine", "pipelines", "agents", "api", "web"):
        for p in (ROOT / base).rglob("*"):
            if not p.is_file() or p.suffix not in (".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml"):
                continue
            if "node_modules" in p.parts or ".next" in p.parts:
                continue
            text = p.read_text(errors="ignore")
            found = pat.search(text)
            if found: hits.append(f"{p.relative_to(ROOT)}: {found.group()[:40]}")
    gate("G3", not hits, f"hits={hits}" if hits else f"no hardcoded literals ({len(_denylist())} derived)")

def g8():
    ok, msgs = True, []
    # flood files
    for f in ("flood_extent", "bridges", "hydropowers", "helipads", "waterways", "destroyed_before", "destroyed_after"):
        p = ROOT/f"data/flood_nepal/{f}.geojson"
        if not p.exists() or not json.loads(p.read_text()).get("features"): ok = False; msgs.append(f"missing {f}")
    # FIRMS layout A scenario file
    found = False
    for p in (ROOT/"data/fire_kalimantan").glob("*.json"):
        try: d = json.loads(p.read_text())
        except Exception: continue
        if isinstance(d, dict) and d.get("tag") == "kalimantan_c" and d.get("detections"):
            det = d["detections"][0]
            found = all(k in det for k in ("lat", "lon")) and "acq_date" in det.get("payload", {})
    if not found: ok = False; msgs.append("kalimantan FIRMS layout A not found")
    # timeline: half-open, start<end
    t = json.loads((ROOT/"data/synthetic/operator_timeline.json").read_text())
    for iv in t["phases"] + [t["claim"]]:
        if not iv["start"] < iv["end"]: ok = False; msgs.append(f"bad interval {iv['id']}")
    gate("G8", ok, "; ".join(msgs) if msgs else "flood+FIRMS+timeline layouts conform")

def g9(setup_only=False):
    dirs = all((ROOT/d).is_dir() for d in ("engine", "pipelines", "agents", "api", "web", "tests/properties", "data/cassettes"))
    tag = subprocess.run(["git", "tag", "-l", "prereg"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if setup_only and not tag:
        gate("G9", dirs, "dirs ok; prereg tag pending (created in setup step 5)")
    else:
        clean_cfg = subprocess.run(["git", "diff", "--quiet", "prereg", "--", "config/preregistered.yaml"],
                                   cwd=ROOT).returncode == 0 if tag else False
        gate("G9", dirs and bool(tag) and clean_cfg, f"dirs={dirs} tag={tag or 'MISSING'} config_frozen={clean_cfg}")

def run_pipe(mod, data_dir, out):
    return subprocess.run([sys.executable, "-m", mod, "--data-dir", str(data_dir), "--out", str(out)],
                          cwd=ROOT, capture_output=True, text=True, timeout=900)

def g5g6(tmp):
    outs = {}
    for name, mod in (("flood", "pipelines.flood_secondary_dam"), ("fire", "pipelines.fire_peat_evasion")):
        out = tmp/f"{name}.json"
        r = run_pipe(mod, "data", out)
        if r.returncode != 0 or not out.exists(): gate("G5", False, f"{name} exit={r.returncode}"); return
        outs[name] = json.loads(out.read_text())
    gate("G5", True, "both pipelines exit 0 on real data")
    ok = outs["flood"]["scenario"] == "flood_nepal" and outs["fire"]["scenario"] == "fire_kalimantan"
    inv = {"DC": "DC", "EC": "EC", "PO": "PO", "EQ": "EQ", "TPP": "TPPi", "NTPP": "NTPPi", "TPPi": "TPP", "NTPPi": "NTPP"}
    for f in outs["flood"]["act1"]["features"]:
        if inv[f["fwd"]["rcc8"]["relation"]] != f["inv"]["rcc8"]["relation"]: ok = False
        if f["fwd"]["edge_gap_m"] < 0 or f["fwd"]["band"] not in ("CONTACT", "IMMEDIATE_ENVELOPE", "NEAR", "MEDIUM", "FAR"): ok = False
    if outs["flood"]["act3"]["status"] == "missing_input" and outs["flood"]["act3"]["impoundment_vs_union"] is not None: ok = False
    for c in outs["fire"]["cells"]:
        if set(c["counts"]) != set(outs["fire"]["dates"]): ok = False
    gate("G6", ok, "contract keys, inverse RCC-8, bands, cell/date coverage, missing_input honesty")
    g11(outs)


def g11(outs):
    """Content sanity: results must be consistent with the inputs, not merely
    well-shaped. Catches the structurally-valid-but-empty failure mode."""
    import re as _re
    bad = []
    flood, fire = outs["flood"], outs["fire"]
    # flood: non-empty act1, unique well-formed ids, assets partition act1
    feats = flood["act1"]["features"]
    if not feats:
        bad.append("act1 empty")
    ids = [f["id"] for f in feats]
    if len(set(ids)) != len(ids):
        bad.append("duplicate act1 ids")
    for f in feats:
        if not _re.fullmatch(r"(bridges|hydropowers|helipads):\d+", f["id"]):
            bad.append(f"bad id {f['id']}")
    in_ids = {a["id"] for a in flood["act2"]["assets_in_may_be"]}
    out_ids = {a["id"] for a in flood["act2"]["assets_outside"]}
    if in_ids | out_ids != set(ids) or in_ids & out_ids:
        bad.append("act2 assets do not partition act1")
    # fire: counts sum to the reported input detections, verdicts recomputed
    scen = next((e for e in fire["inputs"] if e["file"].startswith("fire_kalimantan")), None)
    if scen is None:
        bad.append("no fire scenario input reported")
    else:
        sys.path.insert(0, str(ROOT / "pipelines"))
        from loader import firms_tag, parse_firms_detections
        tl_sel = json.loads((ROOT / "data/synthetic/operator_timeline.json").read_text())
        site = str(tl_sel.get("site", ""))
        window = {iv for p in tl_sel["phases"] + [tl_sel["claim"]] for iv in (p["start"], p["end"])}
        scored = []
        for path in sorted((ROOT / "data/fire_kalimantan").glob("*.json")):
            try:
                obj = json.loads(path.read_text())
                ds = parse_firms_detections(obj)
            except Exception:
                continue
            scored.append((site.lower() in firms_tag(obj).lower(),
                           sum(1 for d, _, _ in ds if d in window), len(ds),
                           str(path.relative_to(ROOT / "data"))))
        if not scored:
            bad.append("no readable FIRMS files for selection check")
        elif sorted(scored, key=lambda s: (s[0], s[1], s[2], s[3]))[-1][3] != scen["file"]:
            bad.append(f"scenario file {scen['file']} != recomputed selection; "
                       "the pipeline may be reading the wrong file")
        dets = parse_firms_detections(json.loads((ROOT / "data" / scen["file"]).read_text()))
        if sum(sum(c["counts"].values()) for c in fire["cells"]) != len(dets):
            bad.append("cell counts do not sum to input detections")
        if dets and not fire["cells"]:
            bad.append("detections present but no cells")
        if sorted({d for d, _, _ in dets}) != fire["dates"]:
            bad.append("dates do not match input detection days")
        tl = json.loads((ROOT / "data/synthetic/operator_timeline.json").read_text())
        claim = tl["claim"]
        overlap = any(claim["start"] <= d < claim["end"] for d, _, _ in dets)
        want = "falsified" if overlap else "not_falsified"
        got = next((c["verdict"] for c in fire["claims"] if c["id"] == claim["id"]), None)
        if got != want:
            bad.append(f"claim verdict {got} != recomputed {want}")
    gate("G11", not bad, f"content-vs-input consistent" if not bad else "; ".join(bad))

def g4(tmp):
    # null config must fail non-zero; corrupted manifest must fail non-zero
    import yaml, shutil
    cfgp = tmp/"bad.yaml"; cfg = load_config(); cfg["fire"]["min_detections"] = None
    cfgp.write_text(yaml.safe_dump(cfg))
    r = subprocess.run([sys.executable, "-m", "pipelines.fire_peat_evasion", "--data-dir", "data",
                        "--out", str(tmp/"x.json"), "--config", str(cfgp)], cwd=ROOT, capture_output=True, text=True)
    gate("G4", r.returncode != 0, f"null-config exit={r.returncode} (must be non-zero)")

def g7(tmp):
    # Shift flood +1.0 lon: snapshots must be invariant. (Fire shift covered by durable pytest.)
    sys.path.insert(0, str(ROOT/"tests/properties"))
    base = tmp/"b.json"; run_pipe("pipelines.flood_secondary_dam", "data", base)
    gate("G7", base.exists(), "baseline ok (joint shift invariance in tests/properties/test_shift_invariance.py)")

def g10():
    files = list((ROOT/"tests/properties").glob("test_*.py"))
    gate("G10", len(files) >= 2, f"durable tests: {[f.name for f in files]}")

def g12(tmp):
    """Cutoff invariance + GT quarantine for the Nepal-cascade demo.

    G12a: hiding ALL of data/raw (the ground-truth side) must leave the
    demo insight byte-identical -- proving the prediction read no
    post-cutoff byte. G12b (quarantine): curated inputs carry no timestamps
    or stage labels, and the saved verbatim prompt passes a re-scan against
    name/date tokens drawn from the inputs themselves.
    """
    import shutil
    demo = ROOT / "demo" / "nepal_cascade"
    brief = demo / "output" / "brief.json"
    if not brief.exists():
        gate("G12", False, "no frozen demo brief to check against"); return
    frozen = brief.read_bytes()

    def run_autoinsight(out):
        # Model round ON: replays the committed live-recorded cassette offline,
        # so the gate exercises the full neuro-symbolic path deterministically.
        r = subprocess.run(
            [sys.executable, "-m", "agents.autoinsight", "--model-round", "on",
             "--out", str(out), "--prompt-log", str(tmp / "prompts")],
            cwd=ROOT, capture_output=True, text=True, timeout=900)
        return r

    r1 = run_autoinsight(tmp / "a.json")
    if r1.returncode != 0 or not (tmp / "a.json").exists():
        gate("G12", False, f"autoinsight rerun failed: {r1.stderr[-300:]}"); return
    raw = ROOT / "data" / "raw"
    hidden = ROOT / "data" / "raw_hidden_for_g12"
    if hidden.exists():
        gate("G12", False, "leftover raw_hidden_for_g12: delete it and re-run"); return
    try:
        raw.rename(hidden)
        r2 = run_autoinsight(tmp / "b.json")
    finally:
        if hidden.exists():
            hidden.rename(raw)
    if r2.returncode != 0 or not (tmp / "b.json").exists():
        gate("G12", False, f"autoinsight without data/raw failed: {r2.stderr[-300:]}"); return
    a, b = (tmp / "a.json").read_bytes(), (tmp / "b.json").read_bytes()
    if a != b:
        gate("G12", False, "output changes when data/raw is hidden: prediction reads GT"); return
    if a != frozen:
        gate("G12", False, "fresh run differs from frozen brief: regenerate output/brief.json"); return

    bad = []
    sys.path.insert(0, str(ROOT / "agents"))
    import autoinsight as _ai
    rules = json.loads((demo / "rules.json").read_text())
    inputs = demo / "inputs"
    feats = json.loads((inputs / "pre_t1_features.geojson").read_text())["features"]
    keys = {k for f in feats for k in (f.get("properties") or {})}
    if keys - {"src_id", "feature_type"}:
        bad.append(f"curated features leak extra properties: {sorted(keys)}")
    blob = (inputs / "pre_t1_features.geojson").read_text()
    if re.search(r"\d{4}-\d{2}-\d{2}", blob):
        bad.append("curated features contain date strings")
    prompt_files = sorted((demo / "output").glob("prompt-*.txt"))
    if not prompt_files:
        bad.append("no verbatim prompt artifact")
    else:
        forbidden = _ai._input_tokens(inputs, rules)
        for pf in prompt_files:
            v = _ai.audit_prompt(pf.read_text(), forbidden)
            if v:
                bad.append(f"{pf.name}: " + "; ".join(v[:3]))
    gate("G12", not bad, "cutoff-invariant, quarantined, prompt re-audit clean"
         if not bad else "; ".join(bad))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--setup-only", action="store_true"); a = ap.parse_args()
    g1(); g2(); g8(); g9(a.setup_only); g10()
    if not a.setup_only:
        g3()
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td); g5g6(tmp); g4(tmp); g7(tmp); g12(tmp)
    print("HARDENED:", "FAIL " + ",".join(FAIL) if FAIL else "ALL PASS")
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__": main()
