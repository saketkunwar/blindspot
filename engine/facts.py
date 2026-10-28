"""Fact catalog: closed op set over curated inputs (Step 1).

Each op is a pure function ``(inputs_by_role, params) -> (value, active)``.
Thresholds come from the caller ``params`` only; this module hardcodes no
domain vocabulary, no distances, and no activation cutoffs.

``inputs_by_role`` maps a domain role name to one of:
  - a GeoJSON FeatureCollection dict (``{"features": [...]}``),
  - a single GeoJSON Feature / geometry dict,
  - a raw list of GeoJSON Feature dicts,
  - an extent dict holding a ``bbox`` key (``extent.json`` style).

Geometry uses the same latitude-corrected equirectangular projection as
``agents/autoinsight.py`` so catalog values reproduce the flood ledger.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

_OPS = (
    "count",
    "near_share",
    "half_share",
    "cluster",
    "area_sum",
    "area_mean",
    "time_stats",
    "spread",
)


def _project(geom):
    """Project a lon/lat shapely geom to local meters."""
    from shapely.ops import transform as _t

    lat0 = geom.centroid.y
    kx = 111320.0 * math.cos(math.radians(lat0))

    def fwd(x, y, z=None):
        return (x * kx, y * 110540.0)

    return _t(fwd, geom)


def _features_of(obj) -> list:
    """Normalize one role value to a list of GeoJSON Feature dicts."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return [f for f in obj if isinstance(f, dict)]
    if not isinstance(obj, dict):
        return []
    if obj.get("type") == "FeatureCollection":
        return list(obj.get("features") or [])
    if obj.get("type") == "Feature":
        return [obj]
    if "bbox" in obj and isinstance(obj["bbox"], (list, tuple)):
        # extent.json style: synthesize the bbox-rectangle polygon feature.
        # This mirrors agents/autoinsight.run, which rebuilds the rectangle
        # from extent["bbox"] before computing the ledger.
        x0, y0, x1, y1 = obj["bbox"]
        return [{
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [[
                [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0],
            ]]},
        }]
    if "coordinates" in obj:
        return [{"type": "Feature", "properties": {}, "geometry": obj}]
    return []


def _geom_of_feature(feature):
    from shapely.geometry import shape as _shape

    g = (feature or {}).get("geometry")
    if not g:
        return None
    try:
        geom = _shape(g)
    except Exception:
        return None
    if geom.is_empty:
        return None
    return geom


def _projected_geoms(role_obj) -> list:
    out = []
    for f in _features_of(role_obj):
        g = _geom_of_feature(f)
        if g is None:
            continue
        out.append(_project(g))
    return out


def _apply_ref_filter(features: list, ref_filter) -> list:
    if not ref_filter:
        return features
    prop = ref_filter.get("property")
    value = ref_filter.get("value")
    return [f for f in features
            if ((f.get("properties") or {}).get(prop)) == value]


def op_count(inputs_by_role: dict, params: dict):
    """Count features in a role. params: {role, min_count}."""
    role = params["role"]
    min_count = params.get("min_count", 1)
    n = len(_features_of(inputs_by_role.get(role)))
    return n, n >= int(min_count)


def _ref_union_m(inputs_by_role, ref_role, ref_filter=None):
    from shapely.ops import unary_union

    feats = _apply_ref_filter(
        _features_of(inputs_by_role.get(ref_role)), ref_filter)
    geoms = []
    for f in feats:
        g = _geom_of_feature(f)
        if g is not None:
            geoms.append(_project(g))
    if not geoms:
        return None
    return unary_union(geoms)


def op_near_share(inputs_by_role: dict, params: dict):
    """Share of source_role within distance_m of ref_role.

    params: {source_role, ref_role, distance_m, threshold,
             ref_filter? {property, value}}.
    """
    source_role = params["source_role"]
    ref_role = params["ref_role"]
    distance_m = float(params["distance_m"])
    threshold = float(params["threshold"])
    ref_filter = params.get("ref_filter")
    src = _projected_geoms(inputs_by_role.get(source_role))
    n = len(src)
    union = _ref_union_m(inputs_by_role, ref_role, ref_filter)
    if n == 0 or union is None:
        return 0.0, False
    near = sum(1 for g in src if g.distance(union) <= distance_m)
    share = round(near / n, 4)
    return share, share > threshold


def _split_point_m(inputs_by_role, boundary_role) -> tuple:
    """Return (split_y_m, up_region_m2, dn_region_m2) for a boundary role."""
    from shapely.geometry import shape as _shape

    feats = _features_of(inputs_by_role.get(boundary_role))
    if not feats:
        raise ValueError(f"empty boundary role {boundary_role!r}")
    geoms = [g for g in (_geom_of_feature(f) for f in feats) if g is not None]
    if not geoms:
        raise ValueError(f"no geometries in boundary role {boundary_role!r}")
    from shapely.ops import unary_union

    # Reference centroid: first (largest-area) boundary geometry, lon/lat.
    geoms.sort(key=lambda g: _project(g).area, reverse=True)
    ref = geoms[0]
    eproj = _project(ref)
    minx, miny, maxx, maxy = eproj.bounds
    lat0_m = _project(ref.centroid).y
    split_m = min(max(lat0_m, miny), maxy)
    full_w = max(maxx - minx, 1.0)
    up_region = full_w * max(maxy - split_m, 1.0)
    dn_region = full_w * max(split_m - miny, 1.0)
    return split_m, up_region, dn_region


def op_half_share(inputs_by_role: dict, params: dict):
    """Share (or density ratio) on one side of a bearing split.

    params: {role, boundary_role, axis ("lat"), mode ("share" |
      "density_ratio"), threshold}. The split is the boundary-role
    centroid latitude; ``mode="share"`` returns the upstream fraction
    (rounded to 4), ``mode="density_ratio"`` the upstream/downstream
    damage-density ratio (rounded to 3), mirroring the flood ledger.
    """
    role = params["role"]
    boundary_role = params["boundary_role"]
    if params.get("axis", "lat") != "lat":
        raise ValueError("only axis='lat' is supported")
    mode = params.get("mode", "share")
    threshold = float(params["threshold"])
    src = _projected_geoms(inputs_by_role.get(role))
    n = len(src)
    if n == 0:
        return (0.0 if mode == "share" else 0.0), False
    split_m, up_region, dn_region = _split_point_m(
        inputs_by_role, boundary_role)
    up_n = sum(1 for g in src if g.centroid.y > split_m)
    dn_n = n - up_n
    if mode == "share":
        share = round(up_n / n, 4)
        return share, share > threshold
    if mode == "density_ratio":
        ratio = (up_n / up_region) / (dn_n / dn_region + 1e-12)
        ratio = min(ratio, 1e6)
        ratio = round(ratio, 3)
        return ratio, ratio > threshold
    raise ValueError(f"unknown half_share mode {mode!r}")


def op_cluster(inputs_by_role: dict, params: dict):
    """Count of source_role within distance_m of a target subset of ref_role.

    params: {source_role, ref_role, distance_m, min_features,
             ref_filter? {property, value}}. Returns (count, hit).
    """
    source_role = params["source_role"]
    ref_role = params["ref_role"]
    distance_m = float(params["distance_m"])
    min_features = int(params["min_features"])
    ref_filter = params.get("ref_filter")
    src = _projected_geoms(inputs_by_role.get(source_role))
    union = _ref_union_m(inputs_by_role, ref_role, ref_filter)
    if union is None or getattr(union, "is_empty", False):
        return 0, False
    near = sum(1 for g in src if g.distance(union) <= distance_m)
    return near, near >= min_features


def _areas_m2(role_obj) -> list:
    areas = []
    for f in _features_of(role_obj):
        g = _geom_of_feature(f)
        if g is None:
            continue
        areas.append(float(_project(g).area))
    return areas


def op_area_sum(inputs_by_role: dict, params: dict):
    """Sum of projected polygon areas for a role. params: {role}."""
    areas = _areas_m2(inputs_by_role.get(params["role"]))
    total = round(sum(areas), 1)
    return total, total > 0


def op_area_mean(inputs_by_role: dict, params: dict):
    """Mean projected polygon area for a role. params: {role}."""
    areas = _areas_m2(inputs_by_role.get(params["role"]))
    if not areas:
        return 0.0, False
    mean = round(sum(areas) / len(areas), 1)
    return mean, mean > 0


def _parse_time(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def op_time_stats(inputs_by_role: dict, params: dict):
    """Distinct times / span / max gap over a time field.

    params: {role, time_field, min_distinct}. value is a dict
    {n_total, n_dated, n_distinct, span_s, max_gap_s};
    active = n_distinct >= min_distinct. Missing fields yield zeros.
    """
    role = params["role"]
    time_field = params["time_field"]
    min_distinct = int(params.get("min_distinct", 1))
    feats = _features_of(inputs_by_role.get(role))
    stamps = []
    for f in feats:
        t = _parse_time((f.get("properties") or {}).get(time_field))
        if t is not None:
            stamps.append(t)
    stamps.sort()
    distinct = sorted(set(stamps))
    if len(distinct) < 2:
        span = 0.0
        max_gap = 0.0
    else:
        span = float(distinct[-1] - distinct[0])
        max_gap = float(max(b - a for a, b in zip(distinct, distinct[1:])))
    value = {
        "n_total": len(feats),
        "n_dated": len(stamps),
        "n_distinct": len(distinct),
        "span_s": span,
        "max_gap_s": max_gap,
    }
    return value, len(distinct) >= min_distinct


def op_spread(inputs_by_role: dict, params: dict):
    """Bounding-box extents of a role in meters.

    params: {role, min_dx_m?, min_dy_m?}. value is
    {dx_m, dy_m, bbox_lonlat}; active = nonempty and extents meet
    the caller minima.
    """
    role = params["role"]
    min_dx = float(params.get("min_dx_m", 0.0))
    min_dy = float(params.get("min_dy_m", 0.0))
    feats = _features_of(inputs_by_role.get(role))
    geoms_lonlat = [g for g in (_geom_of_feature(f) for f in feats)
                    if g is not None]
    if not geoms_lonlat:
        return {"dx_m": 0.0, "dy_m": 0.0, "bbox_lonlat": []}, False
    from shapely.ops import unary_union

    union = unary_union([_project(g) for g in geoms_lonlat])
    minx, miny, maxx, maxy = union.bounds
    lonlat = unary_union(geoms_lonlat).bounds
    value = {
        "dx_m": float(maxx - minx),
        "dy_m": float(maxy - miny),
        "bbox_lonlat": [float(v) for v in lonlat],
    }
    return value, bool(value["dx_m"] >= min_dx and value["dy_m"] >= min_dy)


OPS = {
    "count": op_count,
    "near_share": op_near_share,
    "half_share": op_half_share,
    "cluster": op_cluster,
    "area_sum": op_area_sum,
    "area_mean": op_area_mean,
    "time_stats": op_time_stats,
    "spread": op_spread,
}


def evaluate(op_name: str, inputs_by_role: dict, params: dict):
    """Run one catalog op by name; returns ``(value, active)``."""
    try:
        fn = OPS[op_name]
    except KeyError:
        raise ValueError(f"unknown fact op {op_name!r}; "
                         f"closed set is {sorted(OPS)}") from None
    return fn(inputs_by_role, params)


def load_inputs_by_role(domain: dict, inputs_dir) -> dict:
    """Load curated role payloads named by ``domain.json``.

    Reads each ``domain["inputs"]`` entry ``{"role", "path", ...}`` from
    ``inputs_dir`` (paths are relative to the domain file directory) plus
    the target-reach file when ``domain["target"]`` names one. Returns the
    ``inputs_by_role`` mapping the ops consume. Raises ``FileNotFoundError``
    for a missing curated file.
    """
    import json as _json
    import pathlib as _pl

    inputs_dir = _pl.Path(inputs_dir)
    out: dict = {}
    for entry in domain.get("inputs", []):
        role = entry["role"]
        path = inputs_dir / _pl.Path(entry["path"]).name
        with open(path) as fh:
            out[role] = _json.load(fh)
    target = domain.get("target") or {}
    if target.get("role") == "network" and "target" not in out:
        candidate = inputs_dir / "target_reach.geojson"
        if candidate.is_file():
            with open(candidate) as fh:
                out["target"] = _json.load(fh)
    return out
