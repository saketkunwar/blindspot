#!/usr/bin/env python3
"""Fail if the data directory differs from its MANIFEST.json."""
import argparse, hashlib, json, pathlib, sys
ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default="data"); ap.add_argument("--allow-perturbed", action="store_true")
a = ap.parse_args(); d = pathlib.Path(a.data_dir)
M = json.loads((d / "MANIFEST.json").read_text())
kinds = {"real", "synthetic"} | ({"perturbed"} if a.allow_perturbed else set())
files = {str(f.relative_to(d)): f for f in d.rglob("*") if f.is_file() and f.name != "MANIFEST.json"}
bad = [f"unlisted file: {r}" for r in files if r not in M]
for rel, e in M.items():
    f = files.get(rel)
    if f is None:
        bad.append(f"listed but missing: {rel}"); continue
    if e.get("sha256") != hashlib.sha256(f.read_bytes()).hexdigest(): bad.append(f"hash changed: {rel}")
    if e.get("kind") not in kinds: bad.append(f"bad kind: {rel}")
    if e.get("kind") == "real" and (not e.get("source_url") or "FILL" in e["source_url"]): bad.append(f"real file without source: {rel}")
    if rel.startswith("synthetic/") and e.get("kind") != "synthetic": bad.append(f"synthetic folder, wrong kind: {rel}")
if bad:
    print("\n".join(bad)); sys.exit(1)
print(f"manifest ok ({len(M)} files)")
