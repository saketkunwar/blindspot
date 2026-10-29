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

import json
import os
import pathlib
import subprocess
import sys
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

PIPELINES = {
    "flood": "pipelines.flood_secondary_dam",
    "fire": "pipelines.fire_peat_evasion",
}

# Frozen studies served by /v1/studies/{id}/*. One entry per frozen study;
# a second study (fire) lands here when P0 Step 6 freezes it — no new routes.
STUDIES = {
    "nepal-cascade": {
        "demo_dir": pathlib.Path("demo") / "nepal_cascade",
    },
}

app = FastAPI(title="BlindSpot")


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


def study_brief(study_id: str, mode: str) -> JSONResponse:
    """Frozen prediction brief. Cached = committed artifact; live = symbolic
    recompute (`--model-round off`, deterministic, no key)."""
    _check_mode(mode)
    demo = _study_dir(study_id)
    if mode == "cached":
        return JSONResponse({"mode": "cached",
                             "data": _read_json(demo / "output" / "brief.json",
                                                "no frozen study brief yet")})
    root = _root()
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "brief.json"
        r = subprocess.run(
            [sys.executable, "-m", "agents.autoinsight", "--model-round", "off",
             "--out", str(out), "--prompt-log", tmp],
            cwd=root, capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or not out.exists():
            raise HTTPException(status_code=502,
                                detail="live study run failed: " + r.stderr[-500:])
        try:
            return JSONResponse({"mode": "live", "data": json.loads(out.read_text())})
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=502, detail="live study output unreadable")


def study_geo(study_id: str) -> JSONResponse:
    """Map layers from curated inputs: target reach, outline box, capped
    pre-cutoff damage sample. Static inputs, so always cached."""
    base = _study_dir(study_id) / "inputs"
    try:
        target = json.loads((base / "target_reach.geojson").read_text())["features"]
        extent = json.loads((base / "extent.json").read_text())
        pre = json.loads((base / "pre_t1_features.geojson").read_text())["features"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"study geo inputs unreadable: {e}")
    cap = 500
    pts = [{"type": "Feature", "properties": {"kind": "pre-cutoff damage"},
            "geometry": f["geometry"]} for f in pre[:cap] if f.get("geometry")]
    x0, y0, x1, y1 = extent["bbox"]
    box = {"type": "Feature", "properties": {"kind": "observed flood outline"},
           "geometry": {"type": "Polygon", "coordinates": [[
               [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}
    layers = ([{**f, "properties": {"kind": "target reach"}} for f in target]
              + [box] + pts)
    return JSONResponse({"mode": "cached",
                         "data": {"layers": layers, "sample_cap": cap,
                                  "pre_cutoff_total": len(pre)}})


def study_gt(study_id: str, mode: str) -> JSONResponse:
    """Post-freeze ground-truth check. Cached = committed `gt_check.json`;
    live = rerun `gt_check.py` (read-only, deterministic from frozen inputs,
    so it rewrites identical bytes) and serve the result."""
    _check_mode(mode)
    demo = _study_dir(study_id)
    if mode == "live":
        r = subprocess.run([sys.executable, str(demo / "gt_check.py")],
                           cwd=_root(), capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise HTTPException(status_code=502,
                                detail="live gt check failed: " + r.stderr[-500:])
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
    return {"status": "ok"}


@app.get("/")
def index() -> dict:
    return {"service": "blindspot", "endpoints": ["/health", "/api/results/flood",
                                                  "/api/results/fire", "/api/evidence",
                                                  "/v1/studies",
                                                  "/v1/studies/{id}/brief",
                                                  "/v1/studies/{id}/geo",
                                                  "/v1/studies/{id}/gt"]}


def _results(name: str, mode: str) -> JSONResponse:
    if mode not in ("cached", "live"):
        raise HTTPException(status_code=400, detail="mode must be cached or live")
    data = _load_cached(name) if mode == "cached" else _run_live(name)
    return JSONResponse({"mode": mode, "data": data})


@app.get("/api/results/flood")
def flood_results(mode: str = "cached") -> JSONResponse:
    return _results("flood", mode)


@app.get("/api/results/fire")
def fire_results(mode: str = "cached") -> JSONResponse:
    return _results("fire", mode)


@app.get("/v1/studies")
def studies_list() -> dict:
    return {"studies": [{"id": sid} for sid in sorted(STUDIES)]}


@app.get("/v1/studies/{study_id}/brief")
def v1_study_brief(study_id: str, mode: str = "cached") -> JSONResponse:
    return study_brief(study_id, mode)


@app.get("/v1/studies/{study_id}/geo")
def v1_study_geo(study_id: str) -> JSONResponse:
    return study_geo(study_id)


@app.get("/v1/studies/{study_id}/gt")
def v1_study_gt(study_id: str, mode: str = "cached") -> JSONResponse:
    return study_gt(study_id, mode)


@app.get("/api/demo/nepal-cascade")
def demo_nepal_cascade(mode: str = "cached") -> JSONResponse:
    """Legacy alias of `/v1/studies/nepal-cascade/brief` (same behaviour)."""
    return study_brief("nepal-cascade", mode)


@app.get("/api/demo/nepal-cascade/geo")
def demo_nepal_cascade_geo() -> JSONResponse:
    """Legacy alias of `/v1/studies/nepal-cascade/geo` (same behaviour)."""
    return study_geo("nepal-cascade")


@app.get("/api/evidence")
def evidence() -> JSONResponse:
    path = _root() / "results" / "evidence.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no evidence.json yet (judge-produced, not built here)")
    try:
        return JSONResponse({"mode": "cached", "data": json.loads(path.read_text())})
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="evidence.json unreadable")
