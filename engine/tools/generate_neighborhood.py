#!/usr/bin/env python3
"""T-1.7 Derive the RCC-8 conceptual-neighborhood graph by enumeration.

Two mechanical enumerations (merged as evidence):

* Enum A -- corner 3x3 reference in a 17-cell universe (its 9 cells, the
  7 touching ring cells, one far disjoint cell). Witnesses DC-EC (needs the
  far cell as a disjoint staging ground), TPP-NTPP (needs the strictly
  inside centre cell), EQ, PO, TPP/TPPi.
* Enum B -- centre 2x2 reference in a full 4x4 universe. Witnesses the
  strict-containment-outside family NTPPi (needs margin on every side, which
  a corner reference cannot provide): TPPi-NTPPi, PO-NTPPi (hole-closing).

Deformation rules (both enums): S and S' stay edge-connected, growth adds a
cell edge-adjacent to S, and the toggled cell never CROSSES the reference
boundary (meeting both interior and exterior). A crossing cell teleports
across the contact instant (e.g. DC straight to PO), skipping the state any
continuous path must pass through; teleport jumps are therefore absent.

Self-check: the eight textbook neighborhood edges (Cohn/Gooday/Gotts
lineage) must all be witnessed; the run fails loudly otherwise. Extra
witnessed edges are kept with witness counts as evidence, never dropped.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from shapely.geometry import box
from shapely.ops import unary_union

from engine.qstr_core import RCC8_RELATIONS, rcc8


def _adj(k: int, n: int) -> list[int]:
    i, j = k % n, k // n
    out = []
    if i > 0:
        out.append(k - 1)
    if i < n - 1:
        out.append(k + 1)
    if j > 0:
        out.append(k - n)
    if j < n - 1:
        out.append(k + n)
    return out


def _connected(mask: int, cells: list[int], adj: dict[int, list[int]]) -> bool:
    members = [k for k in cells if mask & (1 << k)]
    if not members:
        return False
    inset = set(members)
    seen, stack = {members[0]}, [members[0]]
    while stack:
        k = stack.pop()
        for nb in adj[k]:
            if nb in inset and nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return seen == inset


def _run(cell_boxes: dict[int, object], universe: list[int], ref, n: int) -> dict[tuple, int]:
    adj = {k: [nb for nb in _adj(k, n) if nb in set(universe)] for k in universe}
    idx = {k: p for p, k in enumerate(universe)}
    geoms: dict[int, object] = {}
    rels: dict[int, str] = {}
    for mask in range(1, 1 << len(universe)):
        real = 0
        for p, k in enumerate(universe):
            if mask & (1 << p):
                real |= 1 << k
        if not _connected(real, universe, adj):
            continue
        geoms[mask] = unary_union([cell_boxes[k] for k in universe if mask & (1 << idx[k])])
        rels[mask] = rcc8(geoms[mask], ref)
    edges: dict[tuple, int] = {}
    for mask in geoms:
        r1 = rels[mask]
        present = {k for k in universe if mask & (1 << idx[k])}
        for k in universe:
            if k in present:
                m2 = mask ^ (1 << idx[k])
                if m2 == 0 or m2 not in geoms:
                    continue
            else:
                if not any(nb in present for nb in adj[k]):
                    continue
                m2 = mask | (1 << idx[k])
            if cell_boxes[k].overlaps(ref):
                continue
            r2 = rels[m2]
            if r1 != r2:
                edges[(r1, r2)] = edges.get((r1, r2), 0) + 1
    return edges


def main() -> None:
    # Enum A: corner 3x3 reference + ring + one far cell.
    boxes_a = {(i, j): box(i, j, i + 1, j + 1) for j in range(5) for i in range(6)}
    ref_a = box(0, 0, 3, 3)
    ua = [(i, j) for j in range(5) for i in range(6)
          if box(i, j, i + 1, j + 1).within(ref_a)
          or (box(i, j, i + 1, j + 1).touches(ref_a) and (i, j) != (4, 0))
          or (i, j) == (4, 0)]
    flat_a = {j * 6 + i: boxes_a[(i, j)] for (i, j) in ua}
    key_a = {(i, j): j * 6 + i for (i, j) in ua}
    edges_a = _run(flat_a, sorted(key_a.values()), ref_a, 6)

    # Enum B: centre 2x2 reference in a full 4x4 universe.
    boxes_b = {k: box(k % 4, k // 4, k % 4 + 1, k // 4 + 1) for k in range(16)}
    edges_b = _run(boxes_b, list(range(16)), box(1, 1, 3, 3), 4)

    edges: dict[tuple, int] = {}
    for e, n in list(edges_a.items()) + list(edges_b.items()):
        edges[e] = edges.get(e, 0) + n

    graph: dict[str, list] = {r: [] for r in RCC8_RELATIONS}
    for (a, b) in sorted(edges):
        graph[a].append(b)

    textbook = {
        ("DC", "EC"), ("EC", "PO"), ("PO", "TPP"), ("PO", "TPPi"),
        ("TPP", "NTPP"), ("TPPi", "NTPPi"), ("TPP", "EQ"), ("TPPi", "EQ"),
    }
    missing = [e for e in textbook if e[1] not in graph[e[0]]]
    if missing:
        raise SystemExit(f"neighborhood derivation missed textbook edges: {missing}")

    out = {
        "method": "connected single-cell toggles, no boundary-crossing toggle cells; two enums merged",
        "neighbors": {r: sorted(v) for r, v in graph.items()},
        "witness_counts": {f"{a}>{b}": n for (a, b), n in sorted(edges.items())},
    }
    dest = pathlib.Path(__file__).resolve().parents[1] / "neighborhood.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {dest}: " + "; ".join(f"{r}={sorted(v)}" for r, v in graph.items()))


if __name__ == "__main__":
    main()
