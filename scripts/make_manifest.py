#!/usr/bin/env python3
"""Create or refresh data/MANIFEST.json. Keeps source_url and license you already filled in."""
import argparse, hashlib, json, pathlib
ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", default="data"); a = ap.parse_args()
d = pathlib.Path(a.data_dir); mf = d / "MANIFEST.json"
old = json.loads(mf.read_text()) if mf.exists() else {}
new = {}
for f in sorted(d.rglob("*")):
    if not f.is_file() or f.name == "MANIFEST.json":
        continue
    rel = str(f.relative_to(d)); prev = old.get(rel, {})
    new[rel] = {"sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                "kind": "synthetic" if rel.startswith("synthetic/") else prev.get("kind", "real"),
                "source_url": prev.get("source_url", "FILL ME"),
                "license": prev.get("license", "FILL ME")}
mf.write_text(json.dumps(new, indent=1) + "\n")
print(f"wrote {mf} with {len(new)} files; fill in every FILL ME before the judge runs")
