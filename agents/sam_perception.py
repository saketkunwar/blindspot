"""T-4.1 SAM 3.1 perception through the Meta Model API, cassette-backed.

Offline-first: a request is served from the disk cache, else from a recorded
cassette in `data/cassettes/` keyed by request hash, else it fails loudly with
CassetteMiss (no invented masks). Every call -- hit or miss -- is appended to
`meta_usage.json` with its hash and timestamp. Masks are GeoJSON polygons,
returned as Shapely geometries.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

MODEL = "sam-3.1"


class CassetteMiss(Exception):
    """No recorded cassette and no live transport for this request."""


def canonical_hash(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


def _log(usage_path: pathlib.Path, entry: dict) -> None:
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(usage_path.read_text()) if usage_path.exists() else []
    log.append(entry)
    usage_path.write_text(json.dumps(log, indent=1) + "\n")


def perceive(
    image_ref: str,
    prompt: str,
    model: str = MODEL,
    cassettes_dir: str | pathlib.Path = "data/cassettes",
    cache_dir: str | pathlib.Path = "results/sam_cache",
    usage_path: str | pathlib.Path = "meta_usage.json",
) -> list[BaseGeometry]:
    """Return mask polygons for (image_ref, prompt). Never invents geometry."""
    request = {"image": image_ref, "prompt": prompt, "model": model}
    digest = canonical_hash(request)
    usage_path, cache_dir, cassettes_dir = map(pathlib.Path, (usage_path, cache_dir, cassettes_dir))
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()

    def done(geoms, source, hit):
        _log(usage_path, {"ts": stamp, "request_hash": digest, "model": model,
                          "hit": hit, "source": source, "n_polygons": len(geoms)})
        return geoms

    cached = cache_dir / f"{digest}.json"
    if cached.exists():
        saved = json.loads(cached.read_text())
        return done([shape(m) for m in saved["response"]["masks"]], "cache", True)
    cassette = cassettes_dir / f"{digest}.json"
    if cassette.exists():
        saved = json.loads(cassette.read_text())
        geoms = [shape(m) for m in saved["response"]["masks"]]
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"request": request, "response": saved["response"],
                                      "cached_at": stamp}) + "\n")
        return done(geoms, "cassette", True)
    _log(usage_path, {"ts": stamp, "request_hash": digest, "model": model,
                      "hit": False, "source": "miss", "n_polygons": 0,
                      "live_key_present": bool(os.environ.get("META_MODEL_API_KEY"))})
    raise CassetteMiss(f"no cassette for request {digest[:16]}... (image={image_ref!r}); "
                       "record one under data/cassettes/ or set META_MODEL_API_KEY with a live transport")
