"""T-5.1 FastAPI: serves results and evidence.json, live and cached modes.

Every response carries its mode label (`cached` = served from results/ as
produced by the pipelines; `live` = freshly recomputed on this request).
Evidence comes from judge runs, not from this repo: when `evidence.json` is
absent the endpoint says so instead of inventing it.

P1 versioned reads: `/v1/studies/{id}/brief`, `/geo`, `/gt` serve the frozen
study artifacts below (one entry per frozen study; currently Study 1 only).
Legacy `/api/...` routes delegate to the same helpers with identical
behaviour. The OpenAPI schema is frozen at `api/openapi.json` (see
`api/export_openapi.py`); `tests/properties/test_api_v1.py` pins the
contract and the schema sync.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import pathlib
import secrets
import subprocess
import sys
import tempfile

_log = logging.getLogger("blindspot.api")


def _ops_log(action: str, **fields) -> None:
    """One structured line per operated request (stdout, JSON)."""
    _log.info(json.dumps({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          "action": action, **fields}, sort_keys=True))

from fastapi import FastAPI, HTTPException, Request

from api import pages as _pages
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

PIPELINES = {
    "flood": "pipelines.flood_secondary_dam",
    "fire": "pipelines.fire_peat_evasion",
}

# Frozen studies served by /v1/studies/{id}/*. One entry per frozen study;
# no new routes per study. Spec-driven studies (ledger_spec in rules) name
# their compute inputs so live recompute runs the right pipeline.
STUDIES = {
    "nepal-cascade": {
        "demo_dir": pathlib.Path("demo") / "nepal_cascade",
    },
    "kalimantan-fire": {
        "demo_dir": pathlib.Path("demo") / "fire_study",
        "spec": {
            "inputs": "demo/fire_study/inputs",
            "rules": "demo/fire_study/rules.json",
            "domain": "demo/fire_study/domain.json",
        },
    },
}

app = FastAPI(title="BlindSpot")

# The web console (another origin: different port) reads every number from
# this API in the browser, so cross-origin reads are allowed. Writes do not
# exist (read-only API); live recompute stays behind the operator token.
# POST is allowed for one side-effect-free replay endpoint
# (/api/demo2/morning-run), which writes nothing persistent.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS", "POST"],
    allow_headers=["Authorization"],
)


def _study_dir(study_id: str) -> pathlib.Path:
    try:
        rel = STUDIES[study_id]["demo_dir"]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown study {study_id!r}")
    return _root() / rel


def _check_mode(mode: str) -> None:
    if mode not in ("cached", "live"):
        raise HTTPException(status_code=400, detail="mode must be cached or live")


def _read_json(path: pathlib.Path, missing_detail: str) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=missing_detail)
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail=f"{path.name} unreadable")


def _store_path() -> pathlib.Path | None:
    """Seeded store, or None when unseeded (no access policy configured)."""
    p = pathlib.Path(os.environ.get("BLINDSPOT_STORE",
                                     str(_root() / "results" / "store.sqlite3")))
    return p if p.is_file() else None


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _operator_ok(request: Request) -> bool:
    """Live recompute needs the operator token — but only when one is
    configured. Unset means dev-open (documented); the two-click replay
    path and the existing suite run keyless in that default."""
    token = os.environ.get("BLINDSPOT_OPERATOR_TOKEN", "")
    if not token:
        return True
    b = _bearer(request)
    return bool(b) and secrets.compare_digest(b, token)


def _require_operator(request: Request) -> None:
    if not _operator_ok(request):
        raise HTTPException(status_code=401,
                            detail="operator token required for live mode")


def _study_ok(study_id: str, request: Request) -> bool:
    """Per-study read tokens (SHA-256 in the store). No store or no token
    row means open. The operator token always bypasses."""
    if _operator_ok(request) and os.environ.get("BLINDSPOT_OPERATOR_TOKEN", ""):
        bearer = _bearer(request)
        if bearer and secrets.compare_digest(bearer,
                                             os.environ["BLINDSPOT_OPERATOR_TOKEN"]):
            return True
    sp = _store_path()
    if sp is None:
        return True
    from store import db as _db
    con = _db.connect(sp)
    try:
        want = _db.study_token_hash(con, study_id)
    finally:
        con.close()
    if not want:
        return True
    b = _bearer(request)
    return bool(b) and secrets.compare_digest(hashlib.sha256(b.encode()).hexdigest(),
                                              want)


def _require_study(study_id: str, request: Request) -> None:
    if not _study_ok(study_id, request):
        raise HTTPException(status_code=401,
                            detail=f"read token required for study {study_id!r}")


def study_brief(study_id: str, mode: str, request: Request) -> JSONResponse:
    """Frozen prediction brief. Cached = committed artifact; live = symbolic
    recompute (`--model-round off`, deterministic, no key)."""
    _check_mode(mode)
    _require_study(study_id, request)
    demo = _study_dir(study_id)
    if mode == "cached":
        _ops_log("study.brief", study=study_id, mode=mode)
        return JSONResponse({"mode": "cached",
                             "data": _read_json(demo / "output" / "brief.json",
                                                "no frozen study brief yet")})
    root = _root()
    _require_operator(request)
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "brief.json"
        spec = STUDIES[study_id].get("spec")
        cmd = [sys.executable, "-m", "agents.autoinsight", "--model-round", "off",
               "--out", str(out), "--prompt-log", tmp]
        if spec is not None:
            cmd += ["--inputs", spec["inputs"], "--rules", spec["rules"],
                    "--domain", spec["domain"]]
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or not out.exists():
            raise HTTPException(status_code=502,
                                detail="live study run failed: " + r.stderr[-500:])
        try:
            data = json.loads(out.read_text())
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=502, detail="live study output unreadable")
        _ops_log("study.brief", study=study_id, mode="live")
        return JSONResponse({"mode": "live", "data": data})


def _geo_parts(study_id: str) -> tuple:
    base = _study_dir(study_id) / "inputs"
    try:
        target = json.loads((base / "target_reach.geojson").read_text())["features"]
        extent = json.loads((base / "extent.json").read_text())
        pre = json.loads((base / "pre_t1_features.geojson").read_text())["features"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"study geo inputs unreadable: {e}")
    return extent, target, pre


def _verified_brief(study_id: str) -> dict:
    """Frozen brief, hash-checked against the store when seeded (fail-closed
    on mismatch); plain file read when unseeded."""
    demo = _study_dir(study_id)
    brief = _read_json(demo / "output" / "brief.json", "no frozen study brief yet")
    sp = _store_path()
    if sp is not None:
        from store import db as _db
        con = _db.connect(sp)
        try:
            pinned = [a for a in _db.artifacts_for(con, study_id) if a["kind"] == "brief"]
        finally:
            con.close()
        if pinned:
            ok, _ = _db.verify_artifact(_root(), pinned[-1])
            if not ok:
                raise HTTPException(status_code=502,
                                    detail="frozen brief fails store hash check")
    return brief


def _gt_after_layers(study_id: str, cap: int = 500) -> tuple:
    """Ground-truth reveal layers: post-event features the brief never saw.
    GT-marked kind, stride-capped deterministically. Display only — no fact
    op reads these; the ledger inputs are untouched."""
    if study_id != "nepal-cascade":
        return [], 0
    try:
        feats = json.loads((_root() / "data" / "flood_nepal"
                            / "destroyed_after.geojson").read_text())["features"]
    except (OSError, json.JSONDecodeError, KeyError):
        return [], 0
    step = max(1, len(feats) // cap)
    layers = []
    for f in feats[::step][:cap]:
        if not isinstance(f.get("geometry"), dict):
            continue
        p = f.get("properties") or {}
        layers.append({"type": "Feature",
                       "properties": {"kind": "ground truth (after)",
                                      "id": p.get("id"),
                                      "label": p.get("name_latin") or p.get("name"),
                                      "status": p.get("status"),
                                      "place": p.get("adm3_name") or p.get("adm2_name")},
                       "geometry": f["geometry"]})
    return layers, len(feats)


def study_geo(study_id: str, request: Request, after: bool = False) -> JSONResponse:
    """Map layers from curated inputs: target reach, outline box, capped
    pre-cutoff damage sample. Static inputs, so always cached. With
    after=True, GT-marked post-event layers are appended for the reveal."""
    _require_study(study_id, request)
    extent, target, pre = _geo_parts(study_id)
    cap = 500
    pts = [{"type": "Feature", "properties": {"kind": "pre-cutoff damage"},
            "geometry": f["geometry"]} for f in pre[:cap] if f.get("geometry")]
    x0, y0, x1, y1 = extent["bbox"]
    box = {"type": "Feature", "properties": {"kind": "observed flood outline"},
           "geometry": {"type": "Polygon", "coordinates": [[
               [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}
    layers = ([{**f, "properties": {"kind": "target reach"}} for f in target]
              + [box] + pts)
    gt_total = 0
    if after:
        gt, gt_total = _gt_after_layers(study_id, cap)
        layers = layers + gt
    _ops_log("study.geo", study=study_id, layers=len(layers), after=after)
    return JSONResponse({"mode": "cached",
                         "data": {"layers": layers, "sample_cap": cap,
                                  "pre_cutoff_total": len(pre),
                                  "gt_after_total": gt_total}})


def study_gt(study_id: str, mode: str, request: Request) -> JSONResponse:
    """Post-freeze ground-truth check. Cached = committed `gt_check.json`;
    live = rerun `gt_check.py` (read-only, deterministic from frozen inputs,
    so it rewrites identical bytes) and serve the result."""
    _check_mode(mode)
    _require_study(study_id, request)
    demo = _study_dir(study_id)
    if mode == "live":
        _require_operator(request)
        r = subprocess.run([sys.executable, str(demo / "gt_check.py")],
                           cwd=_root(), capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise HTTPException(status_code=502,
                                detail="live gt check failed: " + r.stderr[-500:])
    _ops_log("study.gt", study=study_id, mode=mode)
    return JSONResponse({"mode": mode,
                         "data": _read_json(demo / "output" / "gt_check.json",
                                            "no gt check yet (post-freeze artifact)")})


def _root() -> pathlib.Path:
    return pathlib.Path(os.environ.get("BLINDSPOT_ROOT", "."))


def _load_cached(name: str) -> dict:
    path = _root() / "results" / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"no cached {name} results yet (run the pipelines)")
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail=f"cached {name} results unreadable")


def _run_live(name: str) -> dict:
    root = _root()
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / f"{name}.json"
        try:
            r = subprocess.run(
                [sys.executable, "-m", PIPELINES[name], "--data-dir", str(root / "data"),
                 "--out", str(out)],
                cwd=root, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"live {name} run timed out")
        if r.returncode != 0 or not out.exists():
            raise HTTPException(status_code=502,
                                detail=f"live {name} run failed: " + r.stderr[-500:])
        try:
            return json.loads(out.read_text())
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=502, detail=f"live {name} output unreadable")


@app.get("/health")
def health() -> dict:
    """Liveness only. Shape pinned by contract test; detail lives at
    /health/detail so polling stays cheap."""
    return {"status": "ok"}


@app.get("/health/detail")
def health_detail() -> dict:
    """Operator health: per-study brief verification + store presence.

    Always 200; degradation is reported in the body (`status`), so polling
    never mistakes an unreachable check for a healthy one. No recompute.
    """
    studies = {}
    degraded = []
    for study_id in sorted(STUDIES):
        try:
            brief = _verified_brief(study_id)
            studies[study_id] = {"brief": "ok",
                                 "top": brief["mechanisms"][0]["id"]}
        except HTTPException as e:
            studies[study_id] = {"brief": f"fail: {e.detail}"}
            degraded.append(study_id)
    sp = _store_path()
    store = "seeded" if (sp is not None and sp.is_file()) else "unseeded"
    if store != "seeded":
        degraded.append("store")
    return {"status": "degraded" if degraded else "ok",
            "degraded": degraded, "store": store, "studies": studies}


@app.get("/")
def index() -> dict:
    return {"service": "blindspot", "endpoints": ["/health", "/api/results/flood",
                                                  "/api/results/fire", "/api/evidence",
                                                  "/v1/studies",
                                                  "/v1/studies/{id}/brief",
                                                  "/v1/studies/{id}/geo",
                                                  "/v1/studies/{id}/gt",
                                                  "/v1/studies/{id}/page"]}


def _results(name: str, mode: str, request: Request) -> JSONResponse:
    if mode not in ("cached", "live"):
        raise HTTPException(status_code=400, detail="mode must be cached or live")
    if mode == "live":
        _require_operator(request)
    data = _load_cached(name) if mode == "cached" else _run_live(name)
    return JSONResponse({"mode": mode, "data": data})


@app.get("/api/results/flood")
def flood_results(request: Request, mode: str = "cached") -> JSONResponse:
    return _results("flood", mode, request)


@app.get("/api/results/flood/assets")
def flood_assets() -> JSONResponse:
    """Source asset geometries keyed by act-1 feature id (`layer:index`).
    Geometry only — no properties, so no names or timestamps leak. Lets the
    console highlight the exact selected asset against the band context."""
    from pipelines.flood_secondary_dam import LAYER_FILES
    root = _root()
    out = []
    for layer, fname in LAYER_FILES:
        try:
            feats = json.loads((root / "data" / "flood_nepal" / fname).read_text())["features"]
        except (OSError, json.JSONDecodeError, KeyError) as e:
            raise HTTPException(status_code=502, detail=f"asset layer {fname} unreadable: {e}")
        for i, f in enumerate(feats):
            if not isinstance(f.get("geometry"), dict):
                continue
            out.append({"id": f"{layer}:{i}", "geometry": f["geometry"]})
    try:
        ext = json.loads((root / "data" / "flood_nepal" / "flood_extent.geojson").read_text())["features"]
        if ext and isinstance(ext[0].get("geometry"), dict):
            out.append({"id": "flood-extent", "geometry": ext[0]["geometry"]})
    except (OSError, json.JSONDecodeError, KeyError, IndexError) as e:
        raise HTTPException(status_code=502, detail=f"flood extent unreadable: {e}")
    return JSONResponse({"assets": out})


@app.get("/api/results/flood/names")
def flood_names() -> JSONResponse:
    """OSM names keyed by act-1 feature id (`layer:index`), where the source
    data carries one — 39 of 171 bridges, all 10 hydropowers, 1 of 14
    helipads. Separate from /assets (deliberately geometry-only): names
    are display labels, resolved from the manifest-pinned layer files at
    serve time. Unnamed features map to null; callers fall back to the id.
    """
    from pipelines.flood_secondary_dam import LAYER_FILES
    root = _root()
    names = {}
    for layer, fname in LAYER_FILES:
        try:
            feats = json.loads((root / "data" / "flood_nepal" / fname).read_text())["features"]
        except (OSError, json.JSONDecodeError, KeyError) as e:
            raise HTTPException(status_code=502, detail=f"name layer {fname} unreadable: {e}")
        for i, f in enumerate(feats):
            name = (f.get("properties") or {}).get("name") or ""
            names[f"{layer}:{i}"] = name.strip() or None
    _ops_log("results.names", layers=len(LAYER_FILES), named=sum(1 for v in names.values() if v))
    return JSONResponse({"mode": "cached", "data": {"names": names}})


@app.get("/api/results/fire")
def fire_results(request: Request, mode: str = "cached") -> JSONResponse:
    return _results("fire", mode, request)


@app.get("/v1/studies")
def studies_list() -> dict:
    return {"studies": [{"id": sid} for sid in sorted(STUDIES)]}


@app.get("/v1/studies/{study_id}/brief")
def v1_study_brief(study_id: str, request: Request, mode: str = "cached") -> JSONResponse:
    return study_brief(study_id, mode, request)


@app.get("/v1/studies/{study_id}/geo")
def v1_study_geo(study_id: str, request: Request, after: bool = False) -> JSONResponse:
    return study_geo(study_id, request, after=after)


@app.get("/v1/studies/{study_id}/gt")
def v1_study_gt(study_id: str, request: Request, mode: str = "cached") -> JSONResponse:
    return study_gt(study_id, mode, request)


@app.get("/v1/studies/{study_id}/page", response_class=HTMLResponse)
def v1_study_page(study_id: str, request: Request) -> HTMLResponse:
    _require_study(study_id, request)
    demo = _study_dir(study_id)
    brief = _verified_brief(study_id)
    extent, target, pre = _geo_parts(study_id)
    gt_path = demo / "output" / "gt_check.json"
    gt = json.loads(gt_path.read_text()) if gt_path.is_file() else None
    return HTMLResponse(_pages.render_study_page(study_id, brief, extent,
                                                 target, len(pre), gt))


@app.get("/api/demo/nepal-cascade")
def demo_nepal_cascade(request: Request, mode: str = "cached") -> JSONResponse:
    """Legacy alias of `/v1/studies/nepal-cascade/brief` (same behaviour)."""
    return study_brief("nepal-cascade", mode, request)


@app.get("/api/demo/nepal-cascade/geo")
def demo_nepal_cascade_geo(request: Request, after: bool = False) -> JSONResponse:
    """Legacy alias of `/v1/studies/nepal-cascade/geo` (same behaviour)."""
    return study_geo("nepal-cascade", request, after=after)


@app.get("/api/demo/fire-study")
def demo_fire_study(request: Request, mode: str = "cached") -> JSONResponse:
    """Alias of `/v1/studies/kalimantan-fire/brief` (same behaviour)."""
    return study_brief("kalimantan-fire", mode, request)


@app.get("/api/demo/fire-study/geo")
def demo_fire_study_geo(request: Request, after: bool = False) -> JSONResponse:
    """Map layers for the fire demo: the 30 curated grid cells as one
    `fire cell` kind (a color MapPane already knows), plus the study-box
    outline for framing. Static inputs, so always cached. With after=True,
    the October live pull is appended as GT-marked reveal points."""
    _require_study("kalimantan-fire", request)
    demo = _study_dir("kalimantan-fire")
    try:
        cells = json.loads((demo / "inputs" / "cells.geojson").read_text())["features"]
        box = json.loads((demo / "inputs" / "extent.json").read_text())["bbox"]
        dets = json.loads((demo / "inputs" / "detections.geojson").read_text())["features"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"fire geo inputs unreadable: {e}")
    layers = []
    for c in cells:
        props = c.get("properties") or {}
        if not isinstance(c.get("geometry"), dict):
            continue
        layers.append({"type": "Feature",
                       "properties": {"kind": "fire cell", "id": props.get("cell_id"),
                                      "days": props.get("days", []),
                                      "total": props.get("total", 0)},
                       "geometry": c["geometry"]})
    # Detection points ride the same "fire cell" kind the map already knows,
    # so the serving contract (kinds, counts) is unchanged; the heat layer
    # and circles give them glow and body.
    for f in dets:
        dprops = f.get("properties") or {}
        if not isinstance(f.get("geometry"), dict):
            continue
        layers.append({"type": "Feature",
                       "properties": {"kind": "fire cell",
                                      "id": dprops.get("src_id"),
                                      "day": dprops.get("day")},
                       "geometry": f["geometry"]})
    x0, y0, x1, y1 = box
    layers.append({"type": "Feature", "properties": {"kind": "observed fire outline"},
                   "geometry": {"type": "Polygon", "coordinates": [[
                       [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})
    gt_after_total = 0
    if after:
        # October live pull as the reveal: post-cutoff ground truth the
        # September brief never saw. GT-marked kind, display only.
        try:
            import csv as _csv
            with open(_root() / "api" / "demo2_data" / "live_pull_2026-10-30.csv",
                      newline="") as fh:
                for i, r in enumerate(_csv.DictReader(fh)):
                    try:
                        lon, lat = float(r["longitude"]), float(r["latitude"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    layers.append({"type": "Feature",
                                   "properties": {"kind": "ground truth (after)",
                                                  "id": f"live-{i}",
                                                  "day": r.get("acq_date"),
                                                  "label": "October live detection"},
                                   "geometry": {"type": "Point",
                                                "coordinates": [lon, lat]}})
                    gt_after_total += 1
        except OSError:
            pass
    _ops_log("demo.fire.geo", cells=len(layers) - 1, after=after)
    ncells = sum(1 for f in layers
                 if f["properties"].get("kind") == "fire cell"
                 and f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon"))
    return JSONResponse({"mode": "cached",
                         "data": {"layers": layers, "cell_count": ncells,
                                  "gt_after_total": gt_after_total,
                                  "detections": sum(
                                      (f.get("properties") or {}).get("total", 0)
                                      for f in layers if f["properties"].get("kind") == "fire cell"
                                      and f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon"))}})


@app.get("/api/demo2/fire-study")
def demo2_fire_study(request: Request) -> JSONResponse:
    """Demo-2 memory showcase for the fire study: frozen verdict, episode
    census, pattern table, null-test arms, and the hill-climb report.
    Committed snapshot built by `scripts/make_demo2.py`; 404 names the
    regeneration command instead of failing silently."""
    _ops_log("demo2.fire")
    return JSONResponse({"mode": "cached",
                         "data": _read_json(_root() / "api" / "demo2_data" / "fire.json",
                                            "demo2 snapshots not generated yet "
                                            "(run: python scripts/make_demo2.py)")})


@app.get("/api/demo2/nepal-cascade")
def demo2_nepal_cascade(request: Request) -> JSONResponse:
    """Demo-2 memory showcase for the flood study: frozen verdict, the
    byte-identity proof, and why this domain holds no episodes yet."""
    _ops_log("demo2.nepal")
    return JSONResponse({"mode": "cached",
                         "data": _read_json(_root() / "api" / "demo2_data" / "nepal.json",
                                            "demo2 snapshots not generated yet "
                                            "(run: python scripts/make_demo2.py)")})


@app.post("/api/demo2/morning-run")
def demo2_morning_run(request: Request, source: str = "fixture") -> JSONResponse:
    """Run the morning agent as a demo and narrate its steps. Default
    replays the committed pull (no key, no network, deterministic); with
    ?source=live it pulls fresh data when a key is configured, else 400.
    Scratch outputs only — never the operator digest."""
    import csv as _csv
    _ops_log("demo2.morning")
    from collab_agent import morning as _morning
    import yaml as _yaml
    cfg = _yaml.safe_load(
        (_root() / "collab_agent" / "config.yaml").read_text())
    if source == "live":
        from collab_agent import pull as _pull
        try:
            rows = _pull.fetch(cfg["study_box"], cfg["firms"]["day_range"],
                               None, cfg)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        demo = False
    else:
        pull_path = (_root() / "api" / "demo2_data" /
                     "live_pull_2026-10-30.csv")
        with open(pull_path, newline="") as fh:
            rows = list(_csv.DictReader(fh))
        demo = True
    record, steps = _morning.run(rows, None, cfg)
    return JSONResponse({"mode": "demo" if demo else "live",
                         "demo": demo,
                         "as_of": record["date"],
                         "trigger": record["trigger"],
                         "reason": record["reason"],
                         "snippet": record["snippet"],
                         "steps": steps,
                         "matches_frozen": record["matches_frozen"]})


@app.get("/api/demo2/cross-region")
def demo2_cross_region(request: Request) -> JSONResponse:
    """Cross-region study showcase: per-pattern scene breakdown recomputed
    from the memory store, plus the status of the three pending pulls.
    Built by `scripts/make_crossregion.py`."""
    _ops_log("demo2.crossregion")
    return JSONResponse({"mode": "cached",
                         "data": _read_json(_root() / "api" / "demo2_data" / "crossregion.json",
                                            "cross-region snapshot not generated yet "
                                            "(run: python scripts/make_crossregion.py)")})


@app.get("/api/demo2/nepal-chain")
def demo2_nepal_chain(request: Request) -> JSONResponse:
    """Multi-hop algebra showcase: one honest flood chain (bridge, extent,
    may-be band, target reach) with per-hop relations and the composition
    that forces the verdict. Built by `scripts/make_chain.py`."""
    _ops_log("demo2.chain")
    return JSONResponse({"mode": "cached",
                         "data": _read_json(_root() / "api" / "demo2_data" / "chain.json",
                                            "chain snapshot not generated yet "
                                            "(run: python scripts/make_chain.py)")})


@app.get("/api/evidence")
def evidence() -> JSONResponse:
    path = _root() / "results" / "evidence.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no evidence.json yet (judge-produced, not built here)")
    try:
        return JSONResponse({"mode": "cached", "data": json.loads(path.read_text())})
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="evidence.json unreadable")
