#!/usr/bin/env python3
"""One-command operator status (P3): studies, runs, model usage, gates.

Reads only: the seeded store, the model-call usage log, and the setup
gates. Exit 1 when any seeded artifact fails its hash check (actionable
degradation); otherwise 0. Nothing here recomputes or mutates.

Usage:
  python scripts/status.py [--root .]
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _short(h, n=12):
    h = str(h or "")
    return h[:n] if h else "-"


def studies_table(root: pathlib.Path) -> list:
    """Rows: (id, domain, brief_hash, artifacts_ok, artifacts_total, runs)."""
    from store import db as _db
    sp = root / "results" / "store.sqlite3"
    if not sp.is_file():
        return []
    con = _db.connect(sp)
    try:
        rows = []
        for s in _db.list_studies(con):
            arts = _db.artifacts_for(con, s["id"])
            ok = sum(1 for a in arts if _db.verify_artifact(root, a)[0])
            brief = next((a["sha256"] for a in arts if a["kind"] == "brief"), "")
            rows.append((s["id"], s["domain_id"], _short(brief),
                         f"{ok}/{len(arts)}", str(len(_db.runs_for(con, s["id"])))))
        return rows
    finally:
        con.close()


def runs_table(root: pathlib.Path) -> list:
    """Rows: (study, run, inputs, rules, model, cassettes, operator, started)."""
    from store import db as _db
    sp = root / "results" / "store.sqlite3"
    if not sp.is_file():
        return []
    con = _db.connect(sp)
    try:
        rows = []
        for s in _db.list_studies(con):
            for r in _db.runs_for(con, s["id"]):
                rows.append((s["id"], str(r["rowid"]), _short(r["inputs_hash"], 8),
                             _short(r["rules_hash"], 8), r["model_id"] or "-",
                             str(len(r["cassette_hashes"])), r["operator"],
                             str(r["started_at"])[:19]))
        return rows
    finally:
        con.close()


def usage_table(root: pathlib.Path) -> list:
    """Rows: (model, calls, cassette_hits, live_recorded, misses, last_ts)."""
    up = root / "meta_usage.json"
    if not up.is_file():
        return []
    try:
        log = json.loads(up.read_text())
    except ValueError:
        return []
    by_model = {}
    for e in log:
        m = by_model.setdefault(e.get("model", "?"),
                                {"n": 0, "hit": 0, "live": 0, "miss": 0, "last": ""})
        m["n"] += 1
        src = e.get("source", "")
        if src == "cassette":
            m["hit"] += 1
        elif src == "live-recorded":
            m["live"] += 1
        elif src == "miss":
            m["miss"] += 1
        if str(e.get("ts", "")) > m["last"]:
            m["last"] = str(e.get("ts", ""))
    return [(m, str(v["n"]), str(v["hit"]), str(v["live"]), str(v["miss"]),
             v["last"][:19]) for m, v in sorted(by_model.items())]


def _print(title: str, head: tuple, rows: list) -> None:
    print(f"== {title} ==")
    if not rows:
        print("  (none)")
        return
    widths = [len(h) for h in head]
    for r in rows:
        widths = [max(w, len(c)) for w, c in zip(widths, r)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(head, widths)))
    for r in rows:
        print("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    degraded = False
    _print("STUDIES (id, domain, brief, artifacts_ok, runs)",
           ("study", "domain", "brief", "artifacts", "runs"), studies_table(root))
    _print("RUNS (study, run, inputs, rules, model, cassettes, operator, started)",
           ("study", "run", "inputs", "rules", "model", "cass", "operator", "started"),
           runs_table(root))
    _print("MODEL USAGE (model, calls, cassette, live, miss, last)",
           ("model", "calls", "cassette", "live", "miss", "last"), usage_table(root))
    print("== GATES (setup-only) ==")
    r = subprocess.run([sys.executable, "scripts/validate_hardened.py", "--setup-only"],
                       cwd=root, capture_output=True, text=True, timeout=600)
    tail = [ln for ln in r.stdout.splitlines() if ln.startswith("G")] + \
        [r.stdout.splitlines()[-1] if r.stdout else ""]
    for ln in tail:
        print("  " + ln)
        if ln.startswith("G") and " FAIL " in f" {ln} ":
            degraded = True
    if r.returncode != 0:
        degraded = True
    from store import db as _db
    sp = root / "results" / "store.sqlite3"
    if sp.is_file():
        con = _db.connect(sp)
        try:
            for s in _db.list_studies(con):
                for art in _db.artifacts_for(con, s["id"]):
                    ok, _ = _db.verify_artifact(root, art)
                    if not ok:
                        print(f"  DEGRADED: {s['id']}/{art['kind']} fails hash check")
                        degraded = True
        finally:
            con.close()
    else:
        print("  note: store unseeded (run: python scripts/seed_store.py)")
    return 1 if degraded else 0


if __name__ == "__main__":
    sys.exit(main())
