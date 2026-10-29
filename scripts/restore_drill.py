#!/usr/bin/env python3
"""Backup/restore drill (P2 provenance): wipe results/, rebuild, compare.

Rebuilds only from manifest-pinned inputs + committed cassettes:
the two pipelines (deterministic, proven) and the store seed. Reference
hashes are taken from the live results/ before the wipe, so the drill
proves rebuild-identity, not identity with a stale file. On mismatch the
backup is restored and the drill fails loudly; nothing is lost silently.

Usage:
  python scripts/restore_drill.py [--root .]
"""
import argparse, hashlib, json, pathlib, shutil, subprocess, sys, tempfile

FILES = ("flood.json", "fire.json", "store.sqlite3")


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


_TS_RE = None

def _content_key(p: pathlib.Path) -> str:
    """Identity for rebuilt state. Pipeline outputs are byte-compared;
    the store seeds wall-clock timestamps into its rows, so it compares
    by content with timestamps normalized (artifact hashes must match
    exactly — only the seed clock may move)."""
    global _TS_RE
    if _TS_RE is None:
        import re as _re
        _TS_RE = _re.compile(rb"\d{4}-\d{2}-\d{2}T[\d:.+\-Z]*")
    if p.suffix != ".sqlite3":
        return hashlib.sha256(p.read_bytes()).hexdigest()
    import sqlite3 as _sq
    con = _sq.connect(p)
    try:
        parts = []
        for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            parts.append(f"TABLE {t}".encode())
            cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
            parts.append(("COLS " + ",".join(cols)).encode())
            for row in con.execute(f"SELECT * FROM {t} ORDER BY ROWID"):
                parts.append(repr(row).encode())
    finally:
        con.close()
    blob = b"\n".join(parts)
    return hashlib.sha256(_TS_RE.sub(b"<ts>", blob)).hexdigest()


def drill(root: pathlib.Path) -> list:
    """Run the drill. Returns a list of problems (empty = green)."""
    res = root / "results"
    missing = [f for f in FILES if not (res / f).is_file()]
    if missing:
        return [f"no reference to rebuild against (missing results/{f})" for f in missing]
    reference = {f: _content_key(res / f) for f in FILES}
    problems = []
    with tempfile.TemporaryDirectory(prefix="drill_backup_") as td:
        backup = pathlib.Path(td) / "results"
        shutil.move(str(res), str(backup))
        try:
            (res).mkdir(parents=True, exist_ok=True)
            r1 = subprocess.run(
                [sys.executable, "-m", "pipelines.flood_secondary_dam",
                 "--data-dir", "data", "--out", str(res / "flood.json")],
                cwd=root, capture_output=True, text=True, timeout=900)
            r2 = subprocess.run(
                [sys.executable, "-m", "pipelines.fire_peat_evasion",
                 "--data-dir", "data", "--out", str(res / "fire.json")],
                cwd=root, capture_output=True, text=True, timeout=900)
            r3 = subprocess.run(
                [sys.executable, "scripts/seed_store.py"],
                cwd=root, capture_output=True, text=True, timeout=900)
            for r, name in ((r1, "flood pipeline"), (r2, "fire pipeline"), (r3, "seed")):
                if r.returncode != 0:
                    problems.append(f"rebuild {name} failed: {r.stderr[-200:]}")
            if not problems:
                for f in FILES:
                    if not (res / f).is_file():
                        problems.append(f"rebuild missing results/{f}")
                    elif _content_key(res / f) != reference[f]:
                        problems.append(f"results/{f} differs after rebuild")
            if not problems:
                for extra in sorted((backup).iterdir()):
                    if extra.name not in FILES:
                        target = res / extra.name
                        if not target.exists():
                            if extra.is_dir():
                                shutil.copytree(extra, target)
                            else:
                                shutil.copy2(extra, target)
        finally:
            if problems:
                shutil.rmtree(res, ignore_errors=True)
                shutil.move(str(backup), str(res))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    problems = drill(pathlib.Path(a.root))
    if problems:
        print("DRILL FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("DRILL OK: pipelines byte-identical, store content-identical "
          "(seed clock excluded; artifact hashes exact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
