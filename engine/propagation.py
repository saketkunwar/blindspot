"""T-1.3 Composition and propagation.

RCC-8 composition table transcribed from the published RCC-8 table
(Wikipedia "Region connection calculus", Randell/Cui/Cohn lineage) and
checked in-test by converse symmetry, identity laws and the worked example
TPP;EC = {DC, EC}. Allen composition is generated, not transcribed — see
``engine.qstr_core.ALLEN_COMPOSITION``.
"""
from __future__ import annotations

from engine.qstr_core import (
    ALLEN_COMPOSITION,
    ALLEN_INVERSE,
    ALLEN_RELATIONS,
    RCC8_INVERSE,
    RCC8_RELATIONS,
)

_ALL = frozenset(RCC8_RELATIONS)


def _s(*rels: str) -> frozenset:
    return frozenset(rels)


# Rows R1(a,b), columns R2(b,c); entry = possible R(a,c). Column order:
# DC, EC, PO, TPP, NTPP, TPPi, NTPPi, EQ.
_TABLE_ROWS = [
    [_ALL, _s("DC", "EC", "PO", "TPP", "NTPP"), _s("DC", "EC", "PO", "TPP", "NTPP"),
     _s("DC", "EC", "PO", "TPP", "NTPP"), _s("DC", "EC", "PO", "TPP", "NTPP"),
     _s("DC"), _s("DC"), _s("DC")],
    [_s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("DC", "EC", "PO", "TPP", "TPPi", "EQ"),
     _s("DC", "EC", "PO", "TPP", "NTPP"), _s("EC", "PO", "TPP", "NTPP"),
     _s("PO", "TPP", "NTPP"), _s("DC", "EC"), _s("DC"), _s("EC")],
    [_s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("DC", "EC", "PO", "TPPi", "NTPPi"), _ALL,
     _s("PO", "TPP", "NTPP"), _s("PO", "TPP", "NTPP"),
     _s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("PO")],
    [_s("DC"), _s("DC", "EC"), _s("DC", "EC", "PO", "TPP", "NTPP"),
     _s("TPP", "NTPP"), _s("NTPP"), _s("DC", "EC", "PO", "TPP", "TPPi", "EQ"),
     _s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("TPP")],
    [_s("DC"), _s("DC"), _s("DC", "EC", "PO", "TPP", "NTPP"),
     _s("NTPP"), _s("NTPP"), _s("DC", "EC", "PO", "TPP", "NTPP"),
     _ALL, _s("NTPP")],
    [_s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("EC", "PO", "TPPi", "NTPPi"),
     _s("PO", "TPPi", "NTPPi"), _s("PO", "TPP", "TPPi", "EQ"), _s("PO", "TPP", "NTPP"),
     _s("TPPi", "NTPPi"), _s("NTPPi"), _s("TPPi")],
    [_s("DC", "EC", "PO", "TPPi", "NTPPi"), _s("PO", "TPPi", "NTPPi"),
     _s("PO", "TPPi", "NTPPi"), _s("PO", "TPPi", "NTPPi"),
     _s("PO", "TPP", "NTPP", "TPPi", "NTPPi", "EQ"), _s("NTPPi"), _s("NTPPi"), _s("NTPPi")],
    [_s("DC"), _s("EC"), _s("PO"), _s("TPP"), _s("NTPP"), _s("TPPi"), _s("NTPPi"), _s("EQ")],
]

# NOTE: table columns/rows run DC, EC, PO, TPP, NTPP, TPPi, NTPPi, EQ --
# that order is fixed here and must NOT follow RCC8_RELATIONS (EQ sorts 4th).
_TABLE_ORDER = ("DC", "EC", "PO", "TPP", "NTPP", "TPPi", "NTPPi", "EQ")
RCC8_COMPOSITION: dict[str, dict[str, frozenset]] = {
    r1: {r2: cell for r2, cell in zip(_TABLE_ORDER, row)} for r1, row in zip(_TABLE_ORDER, _TABLE_ROWS)
}


def compose_rcc8(r1: str, r2: str) -> frozenset:
    """Possible relations of (a, c) given a R1 b and b R2 c."""
    return RCC8_COMPOSITION[r1][r2]


def compose_allen(r1: str, r2: str) -> frozenset:
    """Possible Allen relations of (x, z) given x R1 y and y R2 z."""
    return ALLEN_COMPOSITION[r1][r2]


def compose_rectangles(rect1: list[str] | tuple, rect2: list[str] | tuple) -> set[tuple[str, str]]:
    """Axis-wise rectangle composition: 169-label pairs consistent with both axes."""
    out = set()
    for rx in ALLEN_COMPOSITION[rect1[0]][rect2[0]]:
        for ry in ALLEN_COMPOSITION[rect1[1]][rect2[1]]:
            out.add((rx, ry))
    return out


def path_consistency(nodes: list, constraints: dict) -> tuple[dict, bool]:
    """Refine an RCC-8 constraint network; returns (refined, contradictory).

    ``constraints`` maps frozenset({i, j}) to allowed base relations.
    Refined maps ordered (i, j) tuples to remaining relations; reverse pairs
    always hold the exact converse set.
    """
    return path_consistency_with(nodes, constraints, compose_rcc8, RCC8_INVERSE, set(RCC8_RELATIONS))


def path_consistency_with(nodes: list, constraints: dict, compose, inverse: dict, universe: set) -> tuple[dict, bool]:
    directed: dict[tuple, set] = {}
    for k, a in enumerate(nodes):
        for b in nodes[k + 1:]:
            rels = set(constraints.get(frozenset((a, b)), universe))
            directed[(a, b)] = set(rels)
            directed[(b, a)] = {inverse[r] for r in rels}

    def shrink(pair: tuple, allowed: set, queue: list) -> bool:
        cur = directed[pair]
        new = cur & allowed
        if new != cur:
            directed[pair] = new
            rev = (pair[1], pair[0])
            directed[rev] = {inverse[r] for r in new}
            for q in (pair, rev):
                if q not in queue:
                    queue.append(q)
        return not new

    queue = [(a, b) for a in nodes for b in nodes if a != b]
    while queue:
        i, j = queue.pop(0)
        if not directed[(i, j)]:
            return directed, True
        for k in nodes:
            if k == i or k == j:
                continue
            allowed: set = set()
            for r1 in directed[(i, k)]:
                for r2 in directed[(k, j)]:
                    allowed |= set(compose(r1, r2))
            if shrink((i, j), allowed, queue):
                return directed, True
    return directed, False


def network_status(refined: dict) -> dict:
    """ENTAILED (one relation left), POSSIBLE (several), CONTRADICTION (none)."""
    out = {}
    for pair, rels in refined.items():
        if len(rels) == 1:
            out[pair] = "ENTAILED"
        elif len(rels) > 1:
            out[pair] = "POSSIBLE"
        else:
            out[pair] = "CONTRADICTION"
    return out
