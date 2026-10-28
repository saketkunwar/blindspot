"""T-1.2/T-1.4/T-1.5/T-1.6 Qualitative space-time core.

RCC-8 classification uses exact Shapely predicates; any coordinate tolerance is
applied once at ingestion (from config), never here. Allen relations come from
endpoints only: an end equal to the other's start is MEETS, never BEFORE.
"""
from __future__ import annotations

import itertools
import math
from typing import Hashable

from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform

RCC8_RELATIONS = ("DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi")
RCC8_INVERSE = {
    "DC": "DC", "EC": "EC", "PO": "PO", "EQ": "EQ",
    "TPP": "TPPi", "NTPP": "NTPPi", "TPPi": "TPP", "NTPPi": "NTPP",
}

ALLEN_RELATIONS = ("b", "m", "o", "s", "d", "f", "eq", "fi", "di", "si", "oi", "mi", "bi")
ALLEN_INVERSE = {
    "b": "bi", "m": "mi", "o": "oi", "s": "si", "d": "di", "f": "fi", "eq": "eq",
    "fi": "f", "di": "d", "si": "s", "oi": "o", "mi": "m", "bi": "b",
}

TILES = ("N", "NE", "E", "SE", "S", "SW", "W", "NW", "O")
BEARINGS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

_M_PER_DEG_LAT = 110540.0
_M_PER_DEG_LON = 111320.0
# Numerical guard for degenerate (point/vertical-line) MBR axes only; the
# ingest coordinate tolerance stays exactly what the config says.
MBR_EPS_DEG = 1e-9


# ---------------------------------------------------------------- Allen (T-1.4)
def allen(a0: Hashable, a1: Hashable, b0: Hashable, b1: Hashable) -> str:
    """Allen base relation of [a0,a1) to [b0,b1) from endpoints only."""
    if not (a0 < a1) or not (b0 < b1):
        raise ValueError("Allen intervals require start < end")
    if a1 < b0:
        return "b"
    if a1 == b0:
        return "m"
    if a0 > b1:
        return "bi"
    if a0 == b1:
        return "mi"
    if a0 == b0:
        if a1 < b1:
            return "s"
        if a1 == b1:
            return "eq"
        return "si"
    if a1 == b1:
        return "f" if a0 > b0 else "fi"
    if a0 < b0:
        if a1 < b1:
            return "o"
        return "di"
    # a0 > b0 from here
    if a1 < b1:
        return "d"
    if a1 > b1:
        return "oi"
    return "f"


def _allen_of_values(x0: int, x1: int, y0: int, y1: int) -> str:
    if x1 < y0:
        return "b"
    if x1 == y0:
        return "m"
    if x0 > y1:
        return "bi"
    if x0 == y1:
        return "mi"
    if x0 == y0:
        if x1 < y1:
            return "s"
        return "si" if x1 > y1 else "eq"
    if x1 == y1:
        return "f" if x0 > y0 else "fi"
    if x0 < y0:
        return "o" if x1 < y1 else "di"
    return "d" if x1 < y1 else ("oi" if x1 > y1 else "f")


def _build_allen_composition() -> dict[str, dict[str, frozenset]]:
    """Exact Allen composition by exhaustive endpoint-order enumeration.

    Every model of (r1, r2) induces a weak order on the six endpoints, and
    every weak order is realised by ranks 1..6, so enumerating all rank
    assignments yields exactly the satisfiable triples.
    """
    table: dict[str, dict[str, set]] = {r: {c: set() for c in ALLEN_RELATIONS} for r in ALLEN_RELATIONS}
    for vals in itertools.product(range(1, 7), repeat=6):
        x0, x1, y0, y1, z0, z1 = vals
        if not (x0 < x1 and y0 < y1 and z0 < z1):
            continue
        r1 = _allen_of_values(x0, x1, y0, y1)
        r2 = _allen_of_values(y0, y1, z0, z1)
        table[r1][r2].add(_allen_of_values(x0, x1, z0, z1))
    return {r: {c: frozenset(s) for c, s in row.items()} for r, row in table.items()}


ALLEN_COMPOSITION: dict[str, dict[str, frozenset]] = _build_allen_composition()


def _axis(ax0: float, ax1: float, bx0: float, bx1: float) -> str:
    if ax0 == ax1:
        ax0 -= MBR_EPS_DEG / 2
        ax1 += MBR_EPS_DEG / 2
    if bx0 == bx1:
        bx0 -= MBR_EPS_DEG / 2
        bx1 += MBR_EPS_DEG / 2
    return allen(ax0, ax1, bx0, bx1)


def rectangle_label(a_mbr: tuple, b_mbr: tuple) -> list[str]:
    """[rx, ry]: Allen relation on west-east and south-north MBR axes."""
    rx = _axis(a_mbr[0], a_mbr[2], b_mbr[0], b_mbr[2])
    ry = _axis(a_mbr[1], a_mbr[3], b_mbr[1], b_mbr[3])
    return [rx, ry]


# ------------------------------------------------------------------ RCC-8 (T-1.2)
def rcc8(a: BaseGeometry, b: BaseGeometry) -> str:
    """Classify the pair into one of the 8 RCC-8 relations. Reads "a rel b"."""
    if a.is_empty or b.is_empty:
        raise ValueError("RCC-8 is undefined for empty geometries")
    if a.equals(b):
        return "EQ"
    if a.disjoint(b):
        return "DC"
    if a.touches(b):
        return "EC"
    if a.contains_properly(b):
        return "NTPPi"
    if a.contains(b):
        return "TPPi"
    if b.contains_properly(a):
        return "NTPP"
    if b.contains(a):
        return "TPP"
    return "PO"


# ------------------------------------------------------------------ Tiles (T-1.5)
def tiles_of(a_mbr: tuple, ref_mbr: tuple) -> list[str]:
    """Tiles of the reference MBR frame that the other MBR touches (closed edges count)."""
    ax0, ay0, ax1, ay1 = a_mbr
    rx0, ry0, rx1, ry1 = ref_mbr
    west = ax0 <= rx0
    east = ax1 >= rx1
    midx = ax1 >= rx0 and ax0 <= rx1
    south = ay0 <= ry0
    north = ay1 >= ry1
    midy = ay1 >= ry0 and ay0 <= ry1
    out = []
    if north and west:
        out.append("NW")
    if north and midx:
        out.append("N")
    if north and east:
        out.append("NE")
    if midy and west:
        out.append("W")
    if midy and midx:
        out.append("O")
    if midy and east:
        out.append("E")
    if south and west:
        out.append("SW")
    if south and midx:
        out.append("S")
    if south and east:
        out.append("SE")
    return out


def bearing_word(a_centroid: tuple, ref_centroid: tuple) -> str:
    """Compass direction of A seen from the reference; "O" when coincident."""
    lat0 = math.radians((a_centroid[1] + ref_centroid[1]) / 2.0)
    dx = (a_centroid[0] - ref_centroid[0]) * math.cos(lat0)
    dy = a_centroid[1] - ref_centroid[1]
    if math.hypot(dx, dy) == 0.0:
        return "O"
    octant = int((math.atan2(dx, dy) + math.pi / 8) // (math.pi / 4)) % 8
    return BEARINGS[octant]


# --------------------------------------------------------------- Distance (T-1.6)
def _local_m(geom: BaseGeometry, lat0_deg: float) -> BaseGeometry:
    lat_r = math.radians(lat0_deg)
    kx = _M_PER_DEG_LON * math.cos(lat_r)
    return shp_transform(lambda x, y, z=None: (x * kx, y * _M_PER_DEG_LAT), geom)


def edge_gap_m(a: BaseGeometry, b: BaseGeometry) -> float:
    """Nearest-edge gap in latitude-corrected planar metres; 0 when connected."""
    if not a.disjoint(b):
        return 0.0
    lat0 = (a.centroid.y + b.centroid.y) / 2.0
    return float(_local_m(a, lat0).distance(_local_m(b, lat0)))


def centroid_dist_km(a: BaseGeometry, b: BaseGeometry) -> float:
    """Haversine centroid distance in kilometres."""
    lon1, lat1 = a.centroid.x, a.centroid.y
    lon2, lat2 = b.centroid.x, b.centroid.y
    r = math.radians
    h = math.sin(r(lat2 - lat1) / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def band_for(gap_m: float, cfg: dict) -> str:
    """Distance band from config thresholds; limits read from config, never literals."""
    d = cfg["distance"]
    if gap_m <= 1e-9:
        return "CONTACT"
    if gap_m < d["immediate_envelope_m"]:
        return "IMMEDIATE_ENVELOPE"
    if gap_m < d["near_km"] * 1000.0:
        return "NEAR"
    if gap_m < d["medium_km"] * 1000.0:
        return "MEDIUM"
    return "FAR"


# ----------------------------------------------------------------- Snapshots
def snapshot_pair(a: BaseGeometry, b: BaseGeometry, cfg: dict) -> tuple[dict, dict]:
    """(fwd, inv) snapshots; inv is the exact inverse of fwd in every layer."""
    rel = rcc8(a, b)
    rect = rectangle_label(a.bounds, b.bounds)
    rect_inv = rectangle_label(b.bounds, a.bounds)
    tiles = tiles_of(a.bounds, b.bounds)
    tiles_inv = tiles_of(b.bounds, a.bounds)
    ca, cb = (a.centroid.x, a.centroid.y), (b.centroid.x, b.centroid.y)
    gap = edge_gap_m(a, b)
    dist = centroid_dist_km(a, b)
    band = band_for(gap, cfg)
    fwd = {
        "rcc8": {"relation": rel, "status": "ENTAILED"},
        "rectangle": rect,
        "tiles": tiles,
        "bearing": bearing_word(ca, cb),
        "edge_gap_m": gap,
        "centroid_dist_km": dist,
        "band": band,
    }
    inv = {
        "rcc8": {"relation": RCC8_INVERSE[rel], "status": "ENTAILED"},
        "rectangle": rect_inv,
        "tiles": tiles_inv,
        "bearing": bearing_word(cb, ca),
        "edge_gap_m": gap,
        "centroid_dist_km": dist,
        "band": band,
    }
    return fwd, inv
