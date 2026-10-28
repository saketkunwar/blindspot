"""T-5.1 FastAPI: serves results and evidence.json, live and cached modes.

Every response carries its mode label (`cached` = served from results/ as
produced by the pipelines; `live` = freshly recomputed on this request).
Evidence comes from judge runs, not from this repo: when `evidence.json` is
absent the endpoint says so instead of inventing it.
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

app = FastAPI(title="BlindSpot")


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
                                                  "/api/results/fire", "/api/evidence"]}


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


@app.get("/api/demo/nepal-cascade")
def demo_nepal_cascade(mode: str = "cached") -> JSONResponse:
    """Serve the Nepal-cascade autoinsight brief. Cached = frozen artifact;
    live = freshly recomputed on this request. Mode is always labelled."""
    if mode not in ("cached", "live"):
        raise HTTPException(status_code=400, detail="mode must be cached or live")
    if mode == "cached":
        path = _root() / "demo" / "nepal_cascade" / "output" / "brief.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="no frozen demo brief yet")
        try:
            return JSONResponse({"mode": "cached", "data": json.loads(path.read_text())})
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=502, detail="frozen demo brief unreadable")
    root = _root()
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "brief.json"
        r = subprocess.run(
            [sys.executable, "-m", "agents.autoinsight", "--model-round", "off",
             "--out", str(out), "--prompt-log", tmp],
            cwd=root, capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or not out.exists():
            raise HTTPException(status_code=502,
                                detail="live demo run failed: " + r.stderr[-500:])
        try:
            return JSONResponse({"mode": "live", "data": json.loads(out.read_text())})
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=502, detail="live demo output unreadable")


@app.get("/api/demo/nepal-cascade/geo")
def demo_nepal_cascade_geo() -> JSONResponse:
    """Pre-cutoff map layers for the demo: target reach, extent outline box,
    and a capped sample of pre-cutoff damage points. Cached mode; the sample
    cap keeps the payload small and is reported in the response."""
    base = _root() / "demo" / "nepal_cascade" / "inputs"
    try:
        target = json.loads((base / "target_reach.geojson").read_text())["features"]
        extent = json.loads((base / "extent.json").read_text())
        pre = json.loads((base / "pre_t1_features.geojson").read_text())["features"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"demo geo inputs unreadable: {e}")
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


@app.get("/api/evidence")
def evidence() -> JSONResponse:
    path = _root() / "results" / "evidence.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no evidence.json yet (judge-produced, not built here)")
    try:
        return JSONResponse({"mode": "cached", "data": json.loads(path.read_text())})
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="evidence.json unreadable")
