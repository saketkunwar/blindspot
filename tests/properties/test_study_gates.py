"""Durable pins for the P0 Step-7 gates (G13/G3b/G15).

The full gates live in scripts/validate_hardened.py; these tests pin the
regression-prone cores: the null-ranking behaviour per study, card
cleanliness per study, and the neutral wording the G3b scan requires
(any reintroduction fails the gate, these tests name the spot).
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.ledger import score_mechanisms
from agents import context_card as cc

STUDIES = ("demo/nepal_cascade", "demo/fire_study")


def _rules(study):
    return json.loads((ROOT / study / "rules.json").read_text())


def test_null_facts_rank_quiet_top():
    # G15 core: with every fact inactive, the caution (quiet) story wins.
    for study in STUDIES:
        rules = _rules(study)
        quiet = rules["caution_prior"]["mechanism"]
        flat = {"facts": {fid: {"value": 0, "active": False, "text": "quiet"}
                          for fid in rules["facts"]}}
        assert score_mechanisms(rules, flat)[0]["id"] == quiet, study


def test_full_evidence_top_is_not_quiet():
    # G15 mirror: on the frozen briefs, the top story is alarming, not quiet.
    for study in STUDIES:
        rules = _rules(study)
        brief = json.loads((ROOT / study / "output" / "brief.json").read_text())
        assert brief["mechanisms"][0]["id"] != rules["caution_prior"]["mechanism"], study


def test_cards_carry_no_dates_or_names():
    # G13 core: committed cards are prompt-clean (names from *name* fields only,
    # the design's redaction boundary; low-cardinality labels are allowed).
    for study in STUDIES:
        demo = ROOT / study
        card = json.loads((demo / "output" / "card.json").read_text())
        text = (demo / "output" / "card.txt").read_text()
        assert not re.search(r"\d{4}-\d{2}-\d{2}", text), study
        assert not re.search(r"\d{4}-\d{2}-\d{2}", json.dumps(card["roles"])), study
        names = set()
        for f in (demo / "inputs").glob("*.geojson"):
            try:
                feats = json.loads(f.read_text()).get("features", [])
            except Exception:
                continue
            for feat in feats:
                for k, v in ((feat.get("properties") or {}).items()):
                    if "name" in k.lower() and isinstance(v, str):
                        names.update(w for w in re.findall(r"[A-Za-z]{3,}", v)
                                     if w[0].isupper() or w.isupper())
        leaks = [w for w in names
                 if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text)]
        assert not leaks, (study, leaks[:5])


def test_builder_prose_stays_domain_neutral():
    # G3b pins: these exact phrasings reintroduce study-distinctive tokens.
    assert "Anonymous areas only" in cc.card_text(
        {"domain": "x", "roles": {}, "time_range": None, "note": "n"})
    fhz = (ROOT / "engine" / "fhz.py").read_text()
    assert "group-containment" not in fhz and "damage for studies" not in fhz
    prop = (ROOT / "engine" / "propagation.py").read_text()
    assert "surviving relations" not in prop
    gate = (ROOT / "agents" / "verification_gate.py").read_text()
    assert "verifies nothing" not in gate
    from agents import setup_study as _ss
    assert not (set(_ss._DEFAULT_QUIET) & {"nothing", "quiescen", "cessation", "suppression"})
