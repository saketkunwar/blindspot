"""Fixed snippet templates plus the number validator.

Snippets are assembled from ledger-block values only — there is no model
prose anywhere in the digest path. validate() extracts every number from
the finished snippet and requires each one to appear in the JSON-serialised
block; a snippet that fails is never written.
"""
import json
import re

_NUMBER = re.compile(r"\d[\d,]*\.?\d*")


def _nums(text):
    return [n.replace(",", "") for n in _NUMBER.findall(text)]


def validate(snippet, block):
    """Return a list of snippet numbers missing from the block (empty ok)."""
    blob = json.dumps(block, default=str)
    missing = []
    for n in _nums(snippet):
        if n not in blob and n.rstrip("0").rstrip(".") not in blob:
            # allow 476 vs 476.0 style float renderings both ways
            try:
                alt = ("%g" % float(n))
            except ValueError:
                alt = None
            if alt is None or alt not in blob:
                missing.append(n)
    return missing


def render(trigger, ctx):
    """ctx: date, count, median, top_id, top_prob, match(episodes/labelled).
    Returns (snippet, block). The block is the ledger of every number used."""
    top_pct = round(ctx["top_prob"] * 100, 2)
    block = {
        "date": ctx["date"],
        "detections": ctx["count"],
        "trailing_median": ctx["median"],
        "top_mechanism": ctx["top_id"],
        "top_support_pct": top_pct,
        "pattern_episodes": ctx["match"]["episodes"],
        "pattern_labelled": ctx["match"]["labelled"],
        "speak_bar": ctx["speak_bar"],
    }
    if trigger == "speak":
        snippet = (
            f"{ctx['date']}: memory speaks. {ctx['match']['labelled']} "
            f"labelled cases under one pattern clear the bar of 5, so the "
            f"brief gains its second ranking beside frozen "
            f"{ctx['top_id']} at {top_pct} support on {ctx['count']} "
            f"detections.")
    elif trigger == "new_shape":
        snippet = (
            f"{ctx['date']}: a new shape. {ctx['count']} detections match "
            f"no stored pattern, so one study is opened and recorded; "
            f"frozen {ctx['top_id']} still leads at {top_pct} support.")
    elif trigger == "spike":
        snippet = (
            f"{ctx['date']}: {ctx['count']} detections against a trailing "
            f"median of {ctx['median']:g}. Frozen rules read "
            f"{ctx['top_id']} at {top_pct} support; the stored pattern "
            f"stands at {ctx['match']['labelled']} of 5 labelled. Watch "
            f"daily counts: near this level the burn run is unbroken.")
    elif trigger == "quiet_after_match":
        snippet = (
            f"{ctx['date']}: {ctx['count']} detections after a matched "
            f"pattern day — a possible first quiet. Nothing is labelled "
            f"this morning; the window closes first, then the record "
            f"decides. Frozen {ctx['top_id']} holds at {top_pct} support.")
    else:
        snippet = (
            f"{ctx['date']}: {ctx['count']} detections, a quiet day. "
            f"Frozen {ctx['top_id']} holds at {top_pct} support; the "
            f"stored pattern stands at {ctx['match']['labelled']} of 5 "
            f"labelled.")
    return snippet, block
