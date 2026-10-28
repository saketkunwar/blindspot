"""Durable tests for the Context Card (offline; deterministic).

The card is the setup round's eyes: it must describe the data richly enough
to frame a study while leaking no place names and no dates. These tests lock
both properties against the flood inputs without naming any place themselves
(tokens are derived from the inputs at test time).
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import context_card as cc

DEMO = ROOT / "demo" / "nepal_cascade"
INPUTS = DEMO / "inputs"

_GENERIC = {"river", "stream", "canal", "dam", "lake", "bridge", "road",
            "power", "project", "station", "upper", "lower", "north", "south",
            "east", "west", "new", "old", "crossing", "over", "aqueduct",
            "crossing", "reservoir", "barrage", "weir", "hydropower", "hydro"}


def _domain():
    return json.loads((DEMO / "domain.json").read_text())


def _name_tokens():
    toks = set()
    ww = json.loads((INPUTS / "waterways.geojson").read_text())
    for f in ww["features"] + json.loads(
            (INPUTS / "target_reach.geojson").read_text())["features"]:
        name = ((f.get("properties") or {}).get("name") or "")
        for w in re.findall(r"[A-Za-z]{3,}", name):
            if w.lower() not in _GENERIC and (w[0].isupper() or w.isupper()):
                toks.add(w)
    assert len(toks) > 5, "token source too thin to prove redaction"
    return toks


def test_card_covers_domain_roles():
    card = cc.build_card(_domain(), INPUTS)
    assert set(card["roles"]) >= {"damage", "network", "boundary"}
    assert card["roles"]["damage"]["count"] > 0
    assert card["redaction_map"], "expected name tokens to redact"


def test_card_text_has_no_dates_or_names(tmp_path):
    card = cc.build_card(_domain(), INPUTS)
    text = cc.card_text(card)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
    leaks = [t for t in _name_tokens() if re.search(
        r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", text)]
    assert not leaks, f"place names leaked into card text: {leaks[:5]}"


def test_card_json_roundtrip_and_hash_stable(tmp_path):
    d = _domain()
    c1 = cc.build_card(d, INPUTS)
    c2 = cc.build_card(d, INPUTS)
    h = lambda c: json.dumps({k: v for k, v in c.items()
                              if k != "generated_at"}, sort_keys=True)
    assert h(c1) == h(c2)
