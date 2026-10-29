#!/usr/bin/env python3
"""Export the BlindSpot API OpenAPI schema (P1, checked into the repo).

Usage:
  python -m api.export_openapi [--out api/openapi.json] [--check]

`--check` exits non-zero when the checked-in schema differs from the app
(the contract test uses it to keep the file in sync with the routes).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.server import app  # noqa: E402


def schema_bytes() -> bytes:
    return (json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n").encode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "api" / "openapi.json"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    fresh = schema_bytes()
    out = pathlib.Path(a.out)
    if a.check:
        if not out.is_file() or out.read_bytes() != fresh:
            print(f"{out} out of sync with api.server routes; regenerate it")
            return 1
        print(f"{out} in sync")
        return 0
    out.write_text(fresh.decode())
    print(f"wrote {out} ({len(fresh)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
