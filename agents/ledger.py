"""Ledger builder: the set of verified facts a brief may cite.

Relations = every RCC-8 / Allen / rectangle label observed in the results.
Numbers = every int/float walked out of the results (bools excluded).
Entities = feature ids, cell ids, claim ids, site, scenarios, layer names.
"""
from __future__ import annotations


def _walk_numbers(node, out: list):
    if isinstance(node, dict):
        for v in node.values():
            _walk_numbers(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_numbers(v, out)
    elif type(node) in (int, float):
        out.append(float(node))


def build_ledger(flood_res: dict, fire_res: dict, timeline: dict) -> dict:
    relations, entities, numbers = set(), set(), []
    for f in flood_res.get("act1", {}).get("features", []):
        relations.add(f["fwd"]["rcc8"]["relation"])
        relations.update(f["fwd"]["rectangle"])
        entities.add(f["id"])
        entities.add(f["layer"])
    for c in fire_res.get("cells", []):
        entities.add(c["id"])
        relations.update(c["rcc8"].values())
    for t in fire_res.get("timeline_relations", []):
        relations.add(t["relation"])
    for claim in fire_res.get("claims", []):
        entities.add(claim["id"])
    entities.add(str(timeline.get("site", "")))
    entities.add(flood_res.get("scenario", ""))
    entities.add(fire_res.get("scenario", ""))
    _walk_numbers(flood_res, numbers)
    _walk_numbers(fire_res, numbers)
    return {"relations": relations, "numbers": numbers, "entities": {e for e in entities if e}}
