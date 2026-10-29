"""FHZ role validation (P2): MUST_BE zones and story polarity, made real.

A MUST_BE zone is a piece of the last-known-wet geometry (gap-auditor
``must_be``). Per zone this module computes three relation families:

- E (extent-topological): RCC-8 of the zone against the known outline.
- R (reach-directional): 9-tiles of the zone MBR against the flood MBR
  plus the compass bearing of the zone centroid from the flood centroid.
- G (group-containment): RCC-8 of the zone against the evidence union
  (assets for pipelines, damage for studies).

The gate is structural, deliberately: every family set must be non-empty
(relations computable, counterparts present). It does NOT require
non-disjointness — 113 of the 418 real flood zones are disjoint from both
the outline and the assets (remote wet network), and failing them would
mistake geography for broken plumbing. Informativeness (non-DC counts)
is reported as diagnostics, not gated.

Stories: every mechanism's supports/opposes must cite real ledger fact
ids with non-empty supports, and the null story (``caution_prior``)
must exist with positive weight. The meta-vocabulary is fact ids plus
mechanism ids — the citable set already enforced on model replies.
"""
from __future__ import annotations

from shapely.geometry import shape as _shape

from engine import qstr_core as _q


class ZoneError(ValueError):
    """A MUST_BE zone (or its counterparts) fails structural validation."""


class StoryError(ValueError):
    """A rules story fails polarity validation against the fact vocabulary."""


def _shape_or_raise(geom: dict, what: str):
    try:
        return _shape(geom)
    except (ValueError, TypeError, AttributeError) as e:
        raise ZoneError(f"{what} is not a geometry: {e}")


def split_zones(must_be_geom: dict) -> list:
    """One zone per member geometry (GeometryCollections split; else one)."""
    g = _shape_or_raise(must_be_geom, "must_be geometry")
    if g.is_empty:
        raise ZoneError("must_be geometry is empty")
    if g.geom_type == "GeometryCollection":
        members = [m for m in g.geoms if not m.is_empty]
        if not members:
            raise ZoneError("must_be collection has no members")
        return members
    return [g]


def zone_relations(zone, extent, group_union, flood_centroid) -> dict:
    """{"E": [...], "R": [...], "G": [...]} relation records for one zone."""
    e_rel = _q.rcc8(zone, extent)
    tiles = _q.tiles_of(zone.bounds, extent.bounds)
    bearing = _q.bearing_word(
        (zone.centroid.x, zone.centroid.y), tuple(flood_centroid))
    g_rel = _q.rcc8(zone, group_union)
    return {
        "E": [f"rcc8:{e_rel}:outline"],
        "R": [f"tile:{t}" for t in tiles] + [f"bearing:{bearing}"],
        "G": [f"rcc8:{g_rel}:evidence"],
    }


def validate_zone(relations: dict) -> tuple[bool, dict]:
    """Structural gate: every family set non-empty. Diagnostics count
    informative (non-DC) relations without gating on them."""
    problems = [f for f in ("E", "R", "G") if not relations.get(f)]
    informative = sum(
        1 for fam in ("E", "G") for r in relations.get(fam, [])
        if ":DC:" not in r)
    return (not problems,
            {"missing_families": problems, "informative": informative})


def validate_zones(zones, extent, group_union, flood_centroid) -> dict:
    """Validate every zone; fail-closed on the first structural breach."""
    ext = extent if hasattr(extent, "geom_type") else _shape_or_raise(extent, "extent")
    grp = (group_union if hasattr(group_union, "geom_type")
           else _shape_or_raise(group_union, "evidence union"))
    checked = []
    informative_total = 0
    for i, z in enumerate(zones):
        zgeom = (z if hasattr(z, "geom_type")
                 else _shape_or_raise(z, f"zone {i}"))
        if zgeom.is_empty:
            raise ZoneError(f"zone {i} is empty")
        rels = zone_relations(zgeom, ext, grp, tuple(flood_centroid))
        ok, diag = validate_zone(rels)
        if not ok:
            raise ZoneError(f"zone {i}: {diag['missing_families']}")
        informative_total += diag["informative"]
        checked.append({"zone": i, "relations": rels, **diag})
    return {"n_zones": len(checked), "informative_total": informative_total,
            "zones": checked}


def validate_stories(rules: dict, fact_ids: set) -> list[str]:
    """Polarity problems for every mechanism; [] means clean."""
    problems = []
    mechs = rules.get("mechanisms", [])
    if not mechs:
        return ["no mechanisms in rules"]
    ids = set()
    for m in mechs:
        mid = m.get("id")
        if not mid:
            problems.append("mechanism without id")
            continue
        ids.add(mid)
        for fid in list(m.get("supports", [])) + list(m.get("opposes", [])):
            if fid not in fact_ids:
                problems.append(f"{mid}: cites unknown fact {fid!r}")
        if not m.get("supports"):
            problems.append(f"{mid}: empty supports")
    null_id = (rules.get("caution_prior") or {}).get("mechanism")
    if null_id not in ids:
        problems.append(f"null story {null_id!r} not among mechanisms")
    elif float((rules.get("caution_prior") or {}).get("weight", 0.0)) <= 0:
        problems.append(f"null story {null_id!r} has no positive weight")
    return problems
