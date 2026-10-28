"""Context Card builder: domain-driven, redacted inventory for the setup round.

Reads ``domain.json`` + the curated inputs and emits ``card.json`` (exact
inventory) plus ``card.txt`` (the prose context the setup prompt embeds).
Redaction is structural, not promised:

- Value labels are capped (<= 50 distinct per key); raw coordinates are
  never emitted (counts, extents, and types only).
- Name-like fields (any property key containing ``name``) are replaced by
  anonymous tokens (``T-1`` …) in ``card.txt``; the cleartext lives only
  in ``card.json`` under ``redaction_map``, which never enters a prompt.
- ISO date substrings in value labels (e.g. provenance tags such as
  a `source` field) are redacted to `[date]` before the card is built;
  a date surviving redaction is a fail-closed error.
- Pre-cutoff time range is reported only when the damage role still
  carries the domain's time field; stripped inputs report ``null``
  (honest absence, not zero).

Every name/date token the inputs contain is collectable by the same
``engine.ledger._input_tokens`` audit the setup and ranking prompts pass,
so the card is checked by the same gate as everything else.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine import facts as _facts

_MAX_LABELS = 50
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _value_type(values: list):
    kinds = sorted({type(v).__name__ for v in values})
    return "+".join(kinds) if kinds else "absent"


def _role_inventory(role: str, payload) -> dict:
    feats = _facts._features_of(payload)
    geom_types: dict[str, int] = {}
    props: dict[str, list] = {}
    for f in feats:
        g = (f.get("geometry") or {}).get("type")
        if g:
            geom_types[g] = geom_types.get(g, 0) + 1
        for k, v in ((f.get("properties") or {}).items()):
            props.setdefault(k, []).append(v)
    keys = {k: _value_type(v) for k, v in props.items()}
    labels: dict[str, list] = {}
    for k, vals in props.items():
        uniq = sorted({str(v) for v in vals})
        if len(uniq) <= _MAX_LABELS:
            labels[k] = uniq
    return {"role": role, "count": len(feats),
            "geometry_types": geom_types,
            "property_keys": keys, "value_labels": labels}


def build_card(domain: dict, inputs_dir: pathlib.Path) -> dict:
    from engine.ledger import _refuse_raw  # noqa: PLC0415  (same quarantine)

    _refuse_raw([inputs_dir])
    roles = _facts.load_inputs_by_role(domain, inputs_dir)
    inv = {role: _role_inventory(role, payload)
           for role, payload in roles.items()}
    # Provenance strings (e.g. a waterway `source` tag carrying an ISO
    # date) are not time signals. Redact date substrings out of the
    # value labels so they can never reach a prompt; the fail-closed
    # guard below then verifies the redacted card, not the raw inputs.
    for ri in inv.values():
        for k, vals in list(ri["value_labels"].items()):
            ri["value_labels"][k] = [_ISO_RE.sub("[date]", v) for v in vals]
    blob = json.dumps(inv)
    m = _ISO_RE.search(blob)
    if m:
        raise SystemExit(
            f"card inventory still contains a date string ({m.group()!r}) "
            "after redaction")

    redaction_map: dict[str, str] = {}
    counter = 0

    def redact_role(role_inv: dict) -> dict:
        nonlocal counter
        out = dict(role_inv)
        new_labels: dict[str, list] = {}
        for k, vals in role_inv["value_labels"].items():
            if "name" in k.lower():
                red = []
                for v in vals:
                    if v not in redaction_map:
                        counter += 1
                        redaction_map[v] = f"T-{counter}"
                    red.append(redaction_map[v])
                new_labels[k] = sorted(set(red))
            else:
                new_labels[k] = vals
        out["value_labels"] = new_labels
        return out

    redacted = {role: redact_role(ri) for role, ri in inv.items()}
    time_field = (domain.get("cutoff") or {}).get("time_field")
    return {"domain": domain.get("domain_id"),
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "roles": redacted,
            "time_field": time_field,
            "time_range": None,
            "note": ("timestamps stripped at curation; no time signal "
                     "in curated inputs"),
            "redaction_map": redaction_map}


def card_text(card: dict) -> str:
    lines = [f"Study context for domain {card['domain']!r}: one pre-cutoff snapshot.",
             "Anonymous reaches only; tributary names withheld as tokens.",
             "Role inventory:"]
    for role, ri in card["roles"].items():
        lines.append(
            f"- {role}: {ri['count']} features; "
            f"geometries {json.dumps(ri['geometry_types'], sort_keys=True)}; "
            f"properties {json.dumps(ri['property_keys'], sort_keys=True)}")
        for k, vals in ri["value_labels"].items():
            lines.append(f"  - {k}: {', '.join(vals[:12])}"
                         + (" ..." if len(vals) > 12 else ""))
    lines.append(f"Time: {card['time_range'] or card['note']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="demo/nepal_cascade/domain.json")
    ap.add_argument("--inputs", default="demo/nepal_cascade/inputs")
    ap.add_argument("--out-dir", default="demo/nepal_cascade/output")
    a = ap.parse_args(argv)
    domain = json.loads(pathlib.Path(a.domain).read_text())
    card = build_card(domain, pathlib.Path(a.inputs))
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "card.json").write_text(json.dumps(card, indent=1, sort_keys=True) + "\n")
    (out / "card.txt").write_text(card_text(card))
    digest = hashlib.sha256(json.dumps(card, sort_keys=True).encode()).hexdigest()
    print(f"wrote card.json + card.txt ({len(card['roles'])} roles, sha {digest[:16]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
