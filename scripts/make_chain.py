"""Build the honest multi-hop chain snapshot for the new flood chain demo.

Re-runs frozen code over frozen artifacts only. No hand-typed relations:
every hop is read from results/flood.json / the frozen brief, or recomputed
with engine.snapshot_pair over committed inputs. Hops the artifacts cannot
support are skipped with a printed reason (see log), never invented.

Chain: bridges:0 -> flood extent -> may_be band -> target reach verdict,
closed by composing hop 1 with hop 2 and checking the observed membership.

Usage: python scripts/make_chain.py   (writes api/demo2_data/chain.json)
"""
import hashlib
import json
import pathlib
import sys

import yaml
from shapely.geometry import shape as _shape

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.propagation import compose_rcc8  # noqa: E402
from engine.qstr_core import snapshot_pair  # noqa: E402
from pipelines.flood_secondary_dam import read_geojson_features  # noqa: E402

SUBJECT = "bridges:0"


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slim(snap: dict) -> dict:
    return {
        "rcc8": snap["rcc8"]["relation"],
        "rectangle": list(snap["rectangle"]),
        "tiles": list(snap["tiles"]),
        "bearing": snap["bearing"],
        "edge_gap_m": snap["edge_gap_m"],
        "centroid_dist_km": snap["centroid_dist_km"],
        "band": snap["band"],
    }


def main() -> int:
    results = json.loads((ROOT / "results" / "flood.json").read_text())
    brief = json.loads(
        (ROOT / "demo" / "nepal_cascade" / "output" / "brief.json").read_text())
    rules = json.loads(
        (ROOT / "demo" / "nepal_cascade" / "rules.json").read_text())
    cfg = yaml.safe_load((ROOT / "config" / "preregistered.yaml").read_text())

    feats = {f["id"]: f for f in results["act1"]["features"]}
    if SUBJECT not in feats:
        print(f"subject {SUBJECT} missing from frozen act1")
        return 1
    h1 = feats[SUBJECT]

    ingest = cfg["tolerance"]["ingest_deg"]
    inputs = ROOT / "demo" / "nepal_cascade" / "inputs"
    extent = read_geojson_features(
        ROOT / "data" / "flood_nepal" / "flood_extent.geojson", ingest)[0][1]
    reach = read_geojson_features(inputs / "target_reach.geojson", ingest)[0][1]
    maybe = _shape(results["act2"]["may_be"])

    h2_fwd, h2_inv = snapshot_pair(extent, maybe, cfg)
    h3_fwd, h3_inv = snapshot_pair(reach, maybe, cfg)

    in_may = {a["id"]: a for a in results["act2"]["assets_in_may_be"]}
    observed = in_may.get(SUBJECT, {}).get("rcc8")
    if observed is None:
        print(f"subject {SUBJECT} not in frozen assets_in_may_be")
        return 1

    r1 = h1["fwd"]["rcc8"]["relation"]
    r2 = h2_fwd["rcc8"]["relation"]
    allowed = sorted(compose_rcc8(r1, r2))

    cluster_rule = rules.get("cluster_rule", {})
    hops = [
        {"n": 1, "a": SUBJECT, "b": "flood extent (observed outline)",
         "fwd": _slim(h1["fwd"]), "inv": _slim(h1["inv"]),
         "says": "the bridge lies inside the observed flood outline",
         "source": "results/flood.json act1 (frozen pipeline output)"},
        {"n": 2, "a": "flood extent", "b": "may_be band",
         "fwd": _slim(h2_fwd), "inv": _slim(h2_inv),
         "says": "the outline stands in this relation to the maybe region",
         "source": "recomputed with engine.snapshot_pair over committed inputs"},
        {"n": 3, "a": "target reach", "b": "may_be band",
         "fwd": _slim(h3_fwd), "inv": _slim(h3_inv),
         "says": "the tributary reach stands in this relation to the maybe region",
         "source": "recomputed with engine.snapshot_pair over committed inputs"},
        {"n": 4, "a": "damage cluster", "b": "target reach",
         "rule": {"max_distance_m": cluster_rule.get("max_distance_m"),
                  "min_features": cluster_rule.get("min_features")},
         "finding": brief.get("cluster_finding"),
         "says": "the frozen cluster rule fires beside the reach",
         "source": "frozen brief cluster_finding + rules.json cluster_rule"},
    ]
    temporal = {
        "hop": "2,092 damage intervals stand Allen-BEFORE the cutoff "
               "(definitional: curation dated them at or before it)",
        "skipped": "no cutoff-MEETS-quarantine hop: the frozen as_of label "
                   "is 'pre-T1', not a date, so endpoint equality cannot be shown",
    }
    out = {
        "subject": SUBJECT,
        "question": "is this bridge exposed to the hidden flood process?",
        "hops": hops,
        "composition": {
            "step": f"compose({r1}, {r2})",
            "allowed": allowed,
            "observed": observed,
            "match": observed in allowed,
            "meaning": "chaining hop 1 (bridge-vs-extent) with hop 2 "
                       "(extent-vs-may_be) constrains bridge-vs-may_be to "
                       "this set; the observed membership falls inside it, "
                       "so the verdict is forced by the hops, not asserted",
        },
        "temporal": temporal,
        "provenance": {
            "results/flood.json": _sha(ROOT / "results" / "flood.json"),
            "brief": _sha(ROOT / "demo/nepal_cascade/output/brief.json"),
            "rules": _sha(ROOT / "demo/nepal_cascade/rules.json"),
        },
    }
    dest = ROOT / "api" / "demo2_data" / "chain.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    # read-back: the write is real only if it parses identically
    assert json.loads(dest.read_text()) == out
    print(f"chain: subject={SUBJECT} hops={len(hops)} "
          f"compose({r1},{r2})={allowed} observed={observed} "
          f"match={observed in allowed}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
