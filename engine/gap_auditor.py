"""T-2.1-T-2.4 Gap auditor: what a sensing gap may hide.

Continuity (T-2.1) and blind-spot bands (T-2.2) are generic; Detector A
(hydrological dipole, T-2.3) and Detector B (alibi evasion, T-2.4) encode the
two scenario hypotheses. Detector A structurally separates prediction from
observation: rivals are built from t0 data plus config BEFORE t1 is read.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import deque

from shapely.geometry.base import BaseGeometry
from shapely.geometry import mapping
from shapely.ops import transform as shp_transform, unary_union

from engine.neighborhood import neighbors, shortest_path
from engine.qstr_core import allen, rcc8
from engine.schemas import DetectorVerdict, Hypothesis, Transition

_M_PER_DEG_LAT = 110540.0
_M_PER_DEG_LON = 111320.0


def _local(geom: BaseGeometry, lat0: float, invert: bool = False) -> BaseGeometry:
    kx = _M_PER_DEG_LON * math.cos(math.radians(lat0))

    def fwd(x, y, z=None):
        return (x * kx, y * _M_PER_DEG_LAT)

    def back(x, y, z=None):
        return (x / kx, y / _M_PER_DEG_LAT)

    return shp_transform(back if invert else fwd, geom)


def buffer_meters(geom: BaseGeometry, meters: float) -> BaseGeometry:
    """Buffer a lon/lat geometry by metres (local equirectangular projection)."""
    lat0 = geom.centroid.y
    return _local(_local(geom, lat0).buffer(meters), lat0, invert=True)


# ------------------------------------------------------- T-2.1 continuity
def check_continuity(entity: str, from_date: str, to_date: str, from_rel: str, to_rel: str) -> Transition:
    """A jump between non-neighbor RCC-8 states is a DISCONTINUOUS_JUMP.

    Missing intermediates are the shortest neighborhood path between the two
    states (exclusive of endpoints); direct neighbors and repeats are
    CONTINUOUS with no missing states.
    """
    if to_rel == from_rel or to_rel in neighbors(from_rel):
        kind, missing = "CONTINUOUS", []
    else:
        kind, missing = "DISCONTINUOUS_JUMP", shortest_path(from_rel, to_rel)
    return Transition(
        entity=entity,
        from_state=f"{entity}@{from_date}",
        to_state=f"{entity}@{to_date}",
        kind=kind,  # type: ignore[arg-type]
        missing_intermediates=missing,
    )


def continuity_series(entity: str, series: list[tuple[str, str]]) -> list[Transition]:
    """Transitions for consecutive (date, relation) pairs."""
    return [
        check_continuity(entity, d0, d1, r0, r1)
        for (d0, r0), (d1, r1) in zip(series, series[1:])
    ]


# --------------------------------------------------- T-2.2 blind-spot bands
def blind_spot_bands(last_geom: BaseGeometry, gap_hours: float, v_max_m_per_hr: float) -> dict:
    """MUST_BE and MAY_BE from the last known state, gap duration and v_max.

    MUST_BE is the last known geometry itself (the minimum anything can be
    claimed about without extra rates); MAY_BE expands it by v_max * hours.
    Returns GeoJSON mappings plus the expansion radius in metres.
    """
    radius = v_max_m_per_hr * gap_hours
    return {
        "must_be": mapping(last_geom),
        "may_be": mapping(buffer_meters(last_geom, radius)),
        "radius_m": radius,
    }


def classify_assets(band_geom: BaseGeometry, assets: list[tuple[str, str, BaseGeometry]]) -> tuple[list, list]:
    """Split (id, layer, geom) assets into inside-band (with rcc8) and outside."""
    inside, outside = [], []
    for aid, layer, geom in assets:
        rel = rcc8(geom, band_geom)
        if rel == "DC":
            outside.append({"id": aid, "layer": layer})
        else:
            inside.append({"id": aid, "layer": layer, "rcc8": rel})
    return inside, outside


# ------------------------------------------------- T-2.3 Detector A (dipole)
def split_reaches(waterway_geoms: list[BaseGeometry], flood_extent: BaseGeometry) -> dict[str, list[int]]:
    """Split waterways per the preregistered neck rule (D-6, QUESTIONS.md).

    Neck = features intersecting the flood extent; the rest split by centroid
    latitude against the flood centroid (Nepal drains south): north = upstream,
    south = downstream. Returns feature indices per reach.
    """
    flat = flood_extent.centroid.y
    reaches: dict[str, list[int]] = {"upstream": [], "neck": [], "downstream": []}
    for i, geom in enumerate(waterway_geoms):
        if geom.intersects(flood_extent):
            reaches["neck"].append(i)
        elif geom.centroid.y >= flat:
            reaches["upstream"].append(i)
        else:
            reaches["downstream"].append(i)
    return reaches


def predict_a_rivals(up_t0: float, down_t0: float) -> list[Hypothesis]:
    """Rival hypotheses from t0 data plus config, BEFORE t1 is read.

    Takes only t0 areas: it is a structural error to pass t1 values here, and
    there is no parameter for them.
    """
    return [
        Hypothesis(
            id="free_drainage",
            supports=["downstream_change_gte_upstream_change"],
            refutes=["upstream_gain_with_downstream_loss"],
            status="OPEN",
        ),
        Hypothesis(
            id="impoundment",
            supports=["upstream_gain_with_downstream_loss"],
            refutes=["same_sign_change", "downstream_led_change"],
            status="OPEN",
        ),
    ]


def judge_detector_a(
    hypotheses: list[Hypothesis],
    up_t0: float,
    down_t0: float,
    up_t1: float,
    down_t1: float,
) -> DetectorVerdict:
    """Judge the t0-built rivals against t1 areas (m2). Opposite-sign change
    (upstream gain, downstream loss) supports an unobserved impoundment."""
    scale = max(abs(up_t0), abs(down_t0), 1.0)
    eps = 0.01 * scale
    d_up, d_down = up_t1 - up_t0, down_t1 - down_t0
    dipole = d_up > eps and d_down < -eps
    decisive = abs(d_up) > eps or abs(d_down) > eps
    hyps = []
    for h in hypotheses:
        status = "OPEN"
        if h.id == "impoundment":
            status = "SUPPORTED" if dipole else ("FALSIFIED" if decisive else "OPEN")
        elif h.id == "free_drainage":
            status = "FALSIFIED" if dipole else ("SUPPORTED" if decisive else "OPEN")
        hyps.append(Hypothesis(id=h.id, supports=h.supports, refutes=h.refutes, status=status))  # type: ignore[arg-type]
    return DetectorVerdict(
        triggered=dipole,
        reason=(
            f"upstream {up_t0:.1f}->{up_t1:.1f} (d={d_up:+.1f}), "
            f"downstream {down_t0:.1f}->{down_t1:.1f} (d={d_down:+.1f}); "
            + ("opposite-sign dipole supports impoundment at the neck." if dipole
               else "no upstream-gain/downstream-loss dipole; impoundment not supported.")
        ),
        hypotheses=hyps,
        evidence=[{"d_upstream": d_up, "d_downstream": d_down, "eps": eps}],
    )


# ------------------------------------------------- T-2.4 Detector B (evasion)
def _next_day(day: str) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()


def _cell_key(cid: str) -> tuple[int, int]:
    lon, lat = cid.split(",")
    return (int(round(float(lon) * 10)), int(round(float(lat) * 10)))


def _connected_components(keys: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    parts = []
    rest = set(keys)
    while rest:
        start = next(iter(rest))
        rest.discard(start)
        comp = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nb in rest:
                    rest.discard(nb)
                    comp.add(nb)
                    queue.append(nb)
        parts.append(comp)
    return parts


def detector_b(
    detections: list[tuple[str, str]],
    claim: dict,
    cfg: dict,
) -> DetectorVerdict:
    """Test a claimed cessation interval against detections (Allen overlap).

    Any detection day overlapping the claim interval falsifies it. Three
    rivals (extinction, smoldering, boundary-hopping) plus the evasion test:
    connected cells whose summed estimated area exceeds `evasion_ha_total`
    while each cell stays below `evasion_ha_per_cell` (area = detections x
    `viirs_pixel_area_ha`, full-period totals per D-4).
    """
    cs, ce, cid = claim["start"], claim["end"], claim["id"]
    overlap, pre_cells, claim_cells, post_cells = [], set(), set(), set()
    for day, cell in detections:
        if day < cs:
            pre_cells.add(cell)
        if allen(day, _next_day(day), cs, ce) not in ("b", "m", "mi", "bi"):
            overlap.append((day, cell))
            claim_cells.add(cell)
        if day >= ce:
            post_cells.add(cell)
    falsified = bool(overlap)
    smolder = bool(claim_cells & pre_cells)
    hopping = bool(claim_cells - pre_cells)

    pixel = cfg["fire"]["viirs_pixel_area_ha"]
    totals: dict[str, int] = {}
    for _, cell in detections:
        totals[cell] = totals.get(cell, 0) + 1
    by_key = {_cell_key(c): c for c in totals}
    evasion, ev_parts = False, []
    for comp in _connected_components(set(by_key)):
        areas = {by_key[k]: totals[by_key[k]] * pixel for k in comp}
        if (sum(areas.values()) > cfg["fire"]["evasion_ha_total"]
                and all(a < cfg["fire"]["evasion_ha_per_cell"] for a in areas.values())):
            evasion = True
            ev_parts.append(sorted(areas))
    hyps = [
        Hypothesis(id=cid, supports=["no_detection_inside_claim"],
                   refutes=["detection_inside_claim"],
                   status="FALSIFIED" if falsified else "SUPPORTED"),  # type: ignore[arg-type]
        Hypothesis(id="extinction", supports=["no_detection_on_or_after_claim"],
                   refutes=["detection_on_or_after_claim"],
                   status="SUPPORTED" if not (claim_cells or post_cells) else "FALSIFIED"),  # type: ignore[arg-type]
        Hypothesis(id="smoldering", supports=["claim_window_detections_in_known_cells"],
                   refutes=["no_claim_window_detection_in_known_cells"],
                   status="SUPPORTED" if smolder else "FALSIFIED"),  # type: ignore[arg-type]
        Hypothesis(id="boundary_hopping", supports=["claim_window_detections_in_new_cells"],
                   refutes=["no_claim_window_detection_in_new_cells"],
                   status="SUPPORTED" if hopping else "FALSIFIED"),  # type: ignore[arg-type]
        Hypothesis(id="evasion", supports=["connected_cells_sum_over_total_each_below_per_cell"],
                   refutes=["no_evasive_patch"],
                   status="SUPPORTED" if evasion else "FALSIFIED"),  # type: ignore[arg-type]
    ]
    return DetectorVerdict(
        triggered=evasion,
        reason=(
            f"claim {cid} [{cs},{ce}): "
            + (f"FALSIFIED by {len(overlap)} detection(s) inside the interval. " if falsified
               else "no detection inside the interval. ")
            + (f"evasive patch(es) {ev_parts}." if evasion else "no evasive patch.")
        ),
        hypotheses=hyps,
        evidence=[{"overlap": overlap[:10], "evasion_patches": ev_parts}],
    )
