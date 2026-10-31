"""Trigger evaluation in fixed priority order. Pure function of today's
numbers plus yesterday's digest line — no I/O, no model, no judgment calls.

Priority (preregistered, reasons in QUESTIONS.md):
  speak  >  new_shape  >  spike  >  quiet_after_match  >  quiet
"""
import statistics


def _median(vals):
    return statistics.median(vals) if vals else 0


def evaluate(today, trailing, match, prev, cfg):
    """today: (date, count). trailing: counts for the previous days, oldest
    first. match: pattern_match dict from study.score. prev: yesterday's
    digest record or None. cfg: collab_agent config triggers block.

    Returns (trigger_id, reason). trigger_id is None only for a plain
    quiet day (yesterday was not a matched pattern)."""
    t = cfg["triggers"]
    date, count = today
    window = trailing[-(t["trailing_days"]):]
    med = _median(window)

    if match["known"] and match["labelled"] >= t["speak_bar"]:
        return ("speak",
                f"{match['labelled']} labelled cases under one pattern: "
                "memory speaks this morning")
    if not match["known"]:
        return ("new_shape",
                "today's signature matches no stored pattern: a new shape")
    if med > 0 and count >= t["spike_multiple"] * med:
        ratio = count / med
        return ("spike",
                f"{count} detections today against a trailing median of "
                f"{med:g} — roughly {ratio:.0f} times the normal level, "
                f"past the {t['spike_multiple']:g}x bar that earns a study")
    if (prev is not None and prev.get("matched_pattern", False)
            and count < t["quiet_max"]):
        return ("quiet_after_match",
                f"{count} detections after a matched-pattern day: "
                "a possible first quiet, labelled only when its window closes")
    return (None, f"{count} detections, no trigger: a quiet day on record")
