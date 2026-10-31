"""Live FIRMS pull. Keys from the environment only — never files or logs.

Request shape per the official FIRMS area API
(https://firms.modaps.eosdis.nasa.gov/api/area/):
  /api/area/csv/[MAP_KEY]/[SOURCE]/[west,south,east,north]/[DAY_RANGE]/[DATE]
SOURCE is VIIRS_NOAA20_NRT; DAY_RANGE is 1..5.
"""
import csv
import io
import os
import urllib.request

API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def _key(cfg: dict) -> str | None:
    for name in cfg["firms"]["key_env"]:
        if os.environ.get(name):
            return os.environ[name]
    return None


def fetch(box: dict, day_range: int, date: str | None,
          cfg: dict, timeout_s: int = 30) -> list[dict]:
    """Pull detections for the box. Raises RuntimeError with a plain
    message on missing key or transport failure (morning.py turns both
    into a skip log, never a faked reading)."""
    key = _key(cfg)
    if not key:
        raise RuntimeError(
            "no FIRMS key in environment "
            f"({'/'.join(cfg['firms']['key_env'])}); skipped")
    coords = f"{box['west']},{box['south']},{box['east']},{box['north']}"
    url = (f"{API_BASE}/{key}/{cfg['firms']['source']}/"
           f"{coords}/{day_range}")
    if date:
        url += f"/{date}"
    req = urllib.request.Request(url, headers={"User-Agent": "blindspot/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"FIRMS fetch failed: {exc}") from exc
    rows = list(csv.DictReader(io.StringIO(text)))
    for r in rows:
        if "acq_date" not in r or "latitude" not in r or "longitude" not in r:
            raise RuntimeError("FIRMS reply lacks acq_date/latitude/longitude")
    return rows
