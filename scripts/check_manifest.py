#!/usr/bin/env python3
"""Fail if the data directory differs from its MANIFEST.json.

Read-only by default (CI posture). Registering a new file is an explicit
operator act, never a hand edit of the JSON::

  python scripts/check_manifest.py --data-dir data \
      --record model_cassettes/<hash>.json \
      --kind synthetic --source-url "..." --license "..."
"""
import argparse, hashlib, json, pathlib, sys


def load_manifest(data_dir: pathlib.Path) -> dict:
    return json.loads((data_dir / "MANIFEST.json").read_text())


def save_manifest(data_dir: pathlib.Path, manifest: dict) -> None:
    (data_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n")


def tree_files(data_dir: pathlib.Path) -> dict:
    return {str(f.relative_to(data_dir)): f for f in data_dir.rglob("*")
            if f.is_file() and f.name != "MANIFEST.json"}


def check(data_dir: pathlib.Path, allow_perturbed: bool = False) -> list:
    M = load_manifest(data_dir)
    kinds = {"real", "synthetic"} | ({"perturbed"} if allow_perturbed else set())
    files = tree_files(data_dir)
    bad = [f"unlisted file: {r}" for r in files if r not in M]
    for rel, e in M.items():
        f = files.get(rel)
        if f is None:
            bad.append(f"listed but missing: {rel}"); continue
        if e.get("sha256") != hashlib.sha256(f.read_bytes()).hexdigest():
            bad.append(f"hash changed: {rel}")
        if e.get("kind") not in kinds:
            bad.append(f"bad kind: {rel}")
        if e.get("kind") == "real" and (not e.get("source_url") or "FILL" in e["source_url"]):
            bad.append(f"real file without source: {rel}")
        if rel.startswith("synthetic/") and e.get("kind") != "synthetic":
            bad.append(f"synthetic folder, wrong kind: {rel}")
    return bad


def record(data_dir: pathlib.Path, rel: str, kind: str, source_url: str,
           license: str) -> str:
    """Register one new file. Refuses anything already listed (no silent
    overwrite) and anything missing on disk. Returns the entry summary."""
    M = load_manifest(data_dir)
    if rel in M:
        raise SystemExit(f"refusing: {rel} already listed (edit discipline: remove first, explicitly)")
    f = data_dir / rel
    if not f.is_file():
        raise SystemExit(f"refusing: {rel} not on disk under {data_dir}")
    if kind == "real" and (not source_url or "FILL" in source_url):
        raise SystemExit("refusing: kind=real needs a real source_url")
    M[rel] = {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
              "kind": kind, "source_url": source_url, "license": license}
    save_manifest(data_dir, M)
    return f"recorded {rel} ({kind})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--allow-perturbed", action="store_true")
    ap.add_argument("--record", default=None, metavar="REL_PATH",
                    help="register one new file instead of checking")
    ap.add_argument("--kind", default=None)
    ap.add_argument("--source-url", default="")
    ap.add_argument("--license", default="")
    a = ap.parse_args(argv)
    d = pathlib.Path(a.data_dir)
    if a.record:
        if a.kind not in ("real", "synthetic", "perturbed"):
            print("--record needs --kind real|synthetic|perturbed"); return 2
        try:
            print(record(d, a.record, a.kind, a.source_url, a.license))
        except SystemExit as e:
            print(e); return 1
        return 0
    bad = check(d, a.allow_perturbed)
    if bad:
        print("\n".join(bad)); return 1
    print(f"manifest ok ({len(load_manifest(d))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
