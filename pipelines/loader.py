"""T-3.1 One loader for all files: manifest + hash check, GeoJSON and FIRMS
parsing, per-input kind report. Findings documented in QUESTIONS.md."""
from __future__ import annotations

import hashlib
import json
import pathlib

from shapely.geometry import shape


class ManifestError(Exception):
    """Raised when a data file is unlisted, hash-changed, or mis-kinded."""


def load_manifest(data_dir: pathlib.Path) -> dict:
    mf = pathlib.Path(data_dir) / "MANIFEST.json"
    try:
        return json.loads(mf.read_text())
    except FileNotFoundError:
        raise ManifestError(f"missing MANIFEST.json in {data_dir}")
    except json.JSONDecodeError as e:
        raise ManifestError(f"MANIFEST.json unreadable: {e}")


def verify_path(path: pathlib.Path, manifest: dict, data_dir: pathlib.Path) -> dict:
    """Check one file against the manifest; return its {file, sha256, kind}."""
    try:
        rel = str(path.relative_to(data_dir))
    except ValueError:
        raise ManifestError(f"file outside --data-dir: {path}")
    entry = manifest.get(rel)
    if entry is None:
        raise ManifestError(f"unlisted file: {rel}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != entry.get("sha256"):
        raise ManifestError(f"hash changed: {rel}")
    if entry.get("kind") not in ("real", "synthetic", "perturbed"):
        raise ManifestError(f"bad kind for {rel}: {entry.get('kind')}")
    return {"file": rel, "sha256": digest, "kind": entry["kind"]}


def _snap_number(value: float, ingest_deg: float) -> float:
    if not ingest_deg:
        return value
    return round(value / ingest_deg) * ingest_deg


def _snap_coords(coords, ingest_deg: float):
    if isinstance(coords, (int, float)):
        return _snap_number(float(coords), ingest_deg)
    return [_snap_coords(c, ingest_deg) for c in coords]


def snap_feature_coords(feature: dict, ingest_deg: float) -> dict:
    """Apply the ingest tolerance once, at ingestion, never in predicates."""
    if ingest_deg and feature.get("geometry") and feature["geometry"].get("coordinates") is not None:
        feature["geometry"]["coordinates"] = _snap_coords(feature["geometry"]["coordinates"], ingest_deg)
    return feature


def read_geojson_features(path: pathlib.Path, ingest_deg: float) -> list[tuple[dict, object]]:
    """Return [(properties, shapely geom)] for features with geometry."""
    obj = json.loads(path.read_text())
    feats = obj.get("features", []) if isinstance(obj, dict) else []
    out = []
    for feat in feats:
        if not isinstance(feat, dict) or not feat.get("geometry"):
            continue
        geom = shape(snap_feature_coords(feat, ingest_deg)["geometry"])
        if not geom.is_empty:
            out.append((feat.get("properties") or {}, geom))
    return out


def read_geojson_raw(path: pathlib.Path) -> dict:
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict) or obj.get("type") != "FeatureCollection":
        raise ManifestError(f"not a GeoJSON FeatureCollection: {path}")
    return obj


# FIRMS layouts observed in the wild (see QUESTIONS.md):
#  A: {"tag", "bbox", "detections": [{lat, lon, valid_time, payload:{acq_date}}]}
#  B: bare list [{latitude, longitude, acq_date, ...}]
#  empty list (no detections in window)
def _records(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("detections", "data", "records", "features", "items", "results"):
            if isinstance(obj.get(key), list):
                return obj[key]
    raise ManifestError("unknown FIRMS layout: expected a list or a dict holding one")


def parse_firms_detections(obj) -> list[tuple[str, float, float]]:
    """Return [(acq_date, lon, lat)] for every detection, sorted for determinism."""
    out = []
    for rec in _records(obj):
        if not isinstance(rec, dict):
            continue
        merged: dict = dict(rec.get("properties", rec) if isinstance(rec.get("properties", rec), dict) else rec)
        payload = rec.get("payload")
        if isinstance(payload, dict):
            for key, val in payload.items():
                merged.setdefault(key, val)
        lat = merged.get("lat", merged.get("latitude"))
        lon = merged.get("lon", merged.get("longitude", merged.get("lng")))
        day = merged.get("acq_date", merged.get("date", merged.get("acquisition_date")))
        if lat is None or lon is None or not day:
            continue
        if isinstance(day, str) and "T" in day:
            day = day[:10]
        else:
            day = str(day)[:10]
        out.append((day, float(lon), float(lat)))
    return sorted(out)


def firms_tag(obj) -> str:
    if isinstance(obj, dict) and isinstance(obj.get("tag"), str):
        return obj["tag"]
    return ""
