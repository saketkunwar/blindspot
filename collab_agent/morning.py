"""Morning run: pull -> study -> decide -> emit.

Modes (exactly one input):
  --live            fetch the last N days from FIRMS (needs a key in the
                    environment; without one it logs "skipped" and exits 0)
  --pull PATH       score a pull CSV (acq_date, longitude, latitude, ...)
  --fixture oct30   the committed 2026-10-30 pull: the offline, deterministic
                    path the gate exercises (no key, no network)

Outputs (unless --out-dir redirects them, as the tests do):
  results/morning/pull_YYYY-MM-DD.json   the raw pull (derived, unversioned)
  results/morning/digest.json            append-only records (derived)
  api/demo2_data/morning.json            latest brief+snippet (committed
                                         deliberately, like the live CSV)

Exit 0 in all honest cases, including quiet days and missing keys.
"""
import argparse
import csv
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from collab_agent import brief as _brief  # noqa: E402
from collab_agent import decide as _decide  # noqa: E402
from collab_agent import digest as _digest  # noqa: E402
from collab_agent import pull as _pull  # noqa: E402
from collab_agent import study as _study  # noqa: E402

PKG = pathlib.Path(__file__).resolve().parent
FIXTURES = {"oct30": ROOT / "api" / "demo2_data" / "live_pull_2026-10-30.csv"}


def _load_cfg():
    return yaml.safe_load((PKG / "config.yaml").read_text())


def _by_day(rows):
    days = {}
    for r in rows:
        days[r["acq_date"]] = days.get(r["acq_date"], 0) + 1
    return sorted(days.items())


def run(rows, prev, cfg, date=None):
    """One morning from pull rows. Pure orchestration; returns
    (record, steps). The steps are the agent narrating its own work for
    the demo page, including how and whether it used memory. Raises on
    validator failure — a snippet that fails its number check is never
    written."""
    by_day = _by_day(rows)
    if date is None:
        date = by_day[-1][0]
    counts = [n for _, n in by_day]
    today = counts[-1]
    trailing = counts[:-1]
    median = statistics.median(trailing[-cfg["triggers"]["trailing_days"]:]) \
        if trailing else 0
    steps = [{"name": "pull", "title": "Pull the sky",
              "detail": f"{len(rows)} detections across {len(by_day)} days "
                        f"({by_day[0][0]} to {by_day[-1][0]})"}]
    res = _study.score(rows)
    top = res["ranking"][0]
    match = res["pattern_match"]
    steps.append({
        "name": "score", "title": "Study it with the frozen rules",
        "detail": f"top story {top['id']} at "
                  f"{round(top['probability'] * 100, 2)} support — "
                  + ("identical to the frozen September ranking."
                     if res["matches_frozen"] else
                     "DIFFERS from the frozen ranking; reported, not adjusted."),
        "matches_frozen": res["matches_frozen"]})
    bar = cfg["triggers"]["speak_bar"]
    if match["known"] and match["labelled"] >= bar:
        mem_detail = (f"signature {res['signature'][:12]}: "
                      f"{match['labelled']} labelled cases clear the bar "
                      f"of {bar} — memory speaks this morning")
    elif match["known"]:
        mem_detail = (f"signature {res['signature'][:12]}: "
                      f"{match['episodes']} past episodes, "
                      f"{match['labelled']} labelled of {bar} needed — "
                      "memory stays silent")
    else:
        mem_detail = (f"signature {res['signature'][:12]} matches no "
                      "stored pattern — memory has nothing to say")
    steps.append({"name": "memory", "title": "Ask the past",
                  "detail": mem_detail,
                  "episodes": match["episodes"],
                  "labelled": match["labelled"],
                  "speak_bar": bar,
                  "speaks": bool(match["known"]
                                 and match["labelled"] >= bar)})
    trigger, reason = _decide.evaluate(
        (date, today), trailing, match, prev, cfg)
    steps.append({"name": "decide", "title": "Decide whether today is studied",
                  "detail": (f"trigger: {trigger} — {reason}" if trigger
                             else f"no trigger — {reason}"),
                  "trigger": trigger})
    ctx = {"date": date, "count": today, "median": median,
           "top_id": top["id"], "top_prob": top["probability"],
           "match": match, "speak_bar": bar}
    snippet, block = _brief.render(trigger, ctx)
    missing = _brief.validate(snippet, block)
    if missing:
        raise RuntimeError(f"snippet numbers not in ledger block: {missing}")
    steps.append({"name": "snippet", "title": "Write the human lines",
                  "detail": snippet + " Every number above was checked "
                                      "against the ledger block first."})
    return ({
        "date": date,
        "trigger": trigger,
        "reason": reason,
        "snippet": snippet,
        "block": block,
        "ranking": [{"id": m["id"], "probability": m["probability"]}
                    for m in res["ranking"]],
        "signature": res["signature"],
        "matches_frozen": res["matches_frozen"],
        "matched_pattern": bool(match["known"]),
        "detections": len(rows),
    }, steps)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true")
    src.add_argument("--pull", default=None)
    src.add_argument("--fixture", default=None, choices=sorted(FIXTURES))
    ap.add_argument("--date", default=None)
    ap.add_argument("--out-dir", default=None,
                    help="redirect results/morning here (tests)")
    ap.add_argument("--no-snapshot", action="store_true",
                    help="skip writing api/demo2_data/morning.json")
    args = ap.parse_args(argv)
    cfg = _load_cfg()

    if args.live:
        try:
            rows = _pull.fetch(cfg["study_box"], cfg["firms"]["day_range"],
                               None, cfg)
        except RuntimeError as exc:
            print(f"morning: {exc}")
            return 0
    else:
        path = FIXTURES[args.fixture] if args.fixture else args.pull
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
    if not rows:
        print("morning: empty pull, nothing studied")
        return 0

    out = (pathlib.Path(args.out_dir) if args.out_dir
           else ROOT / "results" / "morning")
    records = _digest.load(out / "digest.json")
    record, _ = run(rows, _digest.last(records), cfg, date=args.date)
    records = _digest.append(out / "digest.json", record)
    (out / f"pull_{record['date']}.json").write_text(
        json.dumps(rows, indent=1) + "\n")
    if not args.no_snapshot:
        snap = ROOT / "api" / "demo2_data" / "morning.json"
        snap.write_text(json.dumps(
            {"as_of": record["date"], "mode": "cached",
             "trigger": record["trigger"], "reason": record["reason"],
             "snippet": record["snippet"], "block": record["block"],
             "ranking": record["ranking"],
             "matches_frozen": record["matches_frozen"]}, indent=1) + "\n")
        # read-back: the snapshot is real only if it parses identically
        assert json.loads(snap.read_text())["snippet"] == record["snippet"]
    print(f"morning {record['date']}: trigger={record['trigger']} "
          f"({record['reason']})")
    print(record["snippet"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
