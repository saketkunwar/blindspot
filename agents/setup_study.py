"""Setup round: the LLM frames the study, the kernel will compute it.

Generic over studies: every domain word comes from the study
``domain.json`` (ontology, prompt framing, input roles, geometry defaults,
quiet-story keywords) and the ledger built from it. This module keeps only
the loop — prompt, validate, null-test, compare — and hardcodes no domain
vocabulary, distances, filenames, or fact ids.

The model sees ONLY pre-cutoff context (optionally a redacted Context Card
plus anonymized ledger aggregates). It never sees ground truth, place
names, or dates. The draft NEVER overwrites frozen rules: it lands in a
setup report for review, compared against the frozen study (mechanism
overlap, the draft's own ranking of the real ledger, its null red-team).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents import model_call as mc
from agents.context_card import build_card, card_text
from engine import facts as _facts
from engine.ledger import (_prompt_tokens, _refuse_raw, audit_prompt,
                           compute_ledger, load_domain_geometry,
                           score_mechanisms)

_DEFAULT_QUIET = ("quiet", "null", "baseline", "uneventful")


def _quiet_keywords(domain: dict) -> tuple:
    kws = (domain or {}).get("quiet_keywords") or list(_DEFAULT_QUIET)
    return tuple(kws)


def _is_quiet(m: dict, quiet_keywords=None) -> bool:
    blob = f"{m.get('id', '')} {m.get('title', '')}".lower()
    kws = tuple(quiet_keywords) if quiet_keywords else _DEFAULT_QUIET
    return any(k in blob for k in kws)


def geom_rules(domain) -> dict:
    """Ledger-shaping geometry, always from the study domain at runtime."""
    g = load_domain_geometry(domain)
    return {"facts": {}, "mechanisms": [],
            "cluster_rule": {"max_distance_m": g["cluster_distance_m"],
                             "min_features": g["cluster_min_features"]},
            "channel_adjacent_m": g["channel_adjacent_m"]}


def build_prompt(domain: dict, inputs: pathlib.Path, ledger,
                 card: dict | None = None) -> tuple[str, set[str]]:
    ontology = domain.get("ontology", "")
    framing = domain.get("prompt_framing", "")
    lines = [ontology, framing,
             "Propose an OPEN mechanism set that includes a nothing-happens "
             "story with real weight, per-fact weights, and a spatial cluster "
             "rule. Reply with JSON only: {\"mechanisms\": [{\"id\", "
             "\"title\", \"supports\": [fact ids], \"opposes\": [fact ids], "
             "\"prior\"}], \"weights\": {fact id: number}, \"cluster_rule\": "
             "{\"max_distance_m\": number, \"min_features\": number}}. "
             "Cite only ledger facts, using their FULL ids exactly as written "
             "in the ledger lines below; any abbreviated id invalidates the "
             "draft. Assert no outcome."]
    if card is not None:
        lines += ["Study context (redacted inventory):", card_text(card)]
    lines.append("Ledger facts:")
    for fid, f in ledger["facts"].items():
        lines.append(f"- {fid}: {f['text']}")
    prompt = "\n".join(l for l in lines if l) + "\n"
    return prompt, _prompt_tokens(inputs)


def validate_draft(text: str, ledger_ids: set[str],
                   quiet_keywords=None) -> tuple[dict | None, list[str]]:
    try:
        body = json.loads(text)
    except (json.JSONDecodeError, AttributeError):
        return None, ["draft is not JSON"]
    bad = []
    mechs = body.get("mechanisms")
    if not isinstance(mechs, list) or len(mechs) < 2:
        bad.append("need at least two mechanisms")
        mechs = []
    ids: set[str] = set()
    for m in mechs:
        mid = m.get("id", "")
        if not mid or mid in ids:
            bad.append(f"bad/duplicate mechanism id {mid!r}")
        ids.add(mid)
        for side in ("supports", "opposes"):
            for c in m.get(side, []):
                if c not in ledger_ids:
                    bad.append(f"{mid} cites non-ledger fact {c!r}")
    if not any(_is_quiet(m, quiet_keywords) for m in mechs):
        bad.append("no nothing-happens story in the open set")
    for fid in ledger_ids:
        if fid not in body.get("weights", {}):
            bad.append(f"missing weight for {fid}")
    if bad:
        return None, bad
    return body, []


def null_test(draft: dict, quiet_keywords=None) -> tuple[bool, str]:
    """All facts quiet: the quiet story must top with its own weights."""
    flat = {"facts": {fid: {"value": 0, "active": False, "text": "quiet"}
                      for fid in draft["weights"]}}
    quiet_ids = [m["id"] for m in draft["mechanisms"]
                 if _is_quiet(m, quiet_keywords)]
    rules_like = {"mechanisms": draft["mechanisms"],
                  "facts": {fid: {"weight": w} for fid, w in draft["weights"].items()},
                  "caution_prior": {"mechanism": quiet_ids[0] if quiet_ids else "",
                                    "weight": 0.5}}
    top = score_mechanisms(rules_like, flat)[0]["id"]
    return top in quiet_ids, top


def build_ledger(domain: dict, inputs: pathlib.Path, frozen: dict | None = None):
    """Ledger for the setup round, from the study's own rules shape.

    Rules-driven studies (frozen rules carry ``ledger_spec``) build the
    ledger through the spec builder over domain-named roles; otherwise the
    classic four-role path runs unchanged.
    """
    from engine.ledger import compute_ledger_from_spec
    if frozen is not None and isinstance(frozen.get("ledger_spec"), dict):
        roles = _facts.load_inputs_by_role(domain, inputs)
        return compute_ledger_from_spec({"ledger_spec": frozen["ledger_spec"]}, roles)
    roles = _facts.load_inputs_by_role(domain, inputs)
    damage = _facts._features_of(roles.get("damage"))
    network = roles.get("network", {"features": []})
    target = _facts._features_of(roles.get("target"))
    boundary = _facts._features_of(roles.get("boundary"))
    extent_geom = (boundary[0]["geometry"] if boundary
                   else {"type": "Polygon", "coordinates": []})
    return compute_ledger(damage, network, target, extent_geom,
                          geom_rules(domain), domain=domain)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="demo/nepal_cascade/inputs")
    ap.add_argument("--domain", default="demo/nepal_cascade/domain.json")
    ap.add_argument("--frozen-rules", default="demo/nepal_cascade/rules.json")
    ap.add_argument("--brief", default="demo/nepal_cascade/output/brief.json")
    ap.add_argument("--out-dir", default="demo/nepal_cascade/output")
    ap.add_argument("--model", default=None)
    ap.add_argument("--no-card", action="store_true",
                    help="skip the redacted Context Card (ledger only)")
    ap.add_argument("--traces-db", default=None,
                    help="evolution traces store (optional; one row per round)")
    ap.add_argument("--traces-label", default=None,
                    help="run label for the traces row (default: inputs dir name)")
    a = ap.parse_args(argv)

    inputs = pathlib.Path(a.inputs)
    _refuse_raw([inputs])
    domain = json.loads(pathlib.Path(a.domain).read_text())
    quiet_keywords = _quiet_keywords(domain)
    frozen = json.loads(pathlib.Path(a.frozen_rules).read_text())
    ledger_ids = set(frozen["facts"])

    ledger = build_ledger(domain, inputs, frozen)
    card = None if a.no_card else build_card(domain, inputs)
    prompt, forbidden = build_prompt(domain, inputs, ledger, card)
    violations = audit_prompt(prompt, forbidden)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"setup-prompt-{prompt_hash[:16]}.txt").write_text(prompt)
    if violations:
        raise SystemExit("setup prompt audit failed: " + "; ".join(violations))

    model = a.model or mc.DEFAULT_MODEL
    try:
        res = mc.complete(prompt, model=model)
    except mc.CassetteMiss as e:
        print(f"setup round miss: {e}")
        return 2
    draft, errors = validate_draft(res["text"], ledger_ids, quiet_keywords)

    report = {
        "model": model, "source": res["source"],
        "request_hash": res["request_hash"],
        "prompt_sha256": prompt_hash,
        "prompt_audit_violations": [],
        "card_used": card is not None,
        "draft_errors": errors,
        "draft": draft,
        "frozen_mechanisms": [m["id"] for m in frozen["mechanisms"]],
        "overlap": sorted(set(m.get("id", "") for m in (draft or {}).get(
            "mechanisms", [])) & set(m["id"] for m in frozen["mechanisms"]))
        if draft else [],
        "null_test_pass": null_test(draft, quiet_keywords)[0] if draft else False,
        "null_test_top": null_test(draft, quiet_keywords)[1] if draft else None,
    }
    if draft:
        quiet_ids = [m["id"] for m in draft["mechanisms"]
                     if _is_quiet(m, quiet_keywords)]
        rules_like = {"mechanisms": draft["mechanisms"],
                      "facts": {fid: {"weight": w}
                                for fid, w in draft["weights"].items()},
                      "caution_prior": {"mechanism": quiet_ids[0] if quiet_ids else "",
                                        "weight": 0.5}}
        draft_ranking = score_mechanisms(rules_like, ledger)
        report["draft_ranking_on_real_ledger"] = [o["id"] for o in draft_ranking]
        report["draft_top"] = draft_ranking[0]["id"]
        report["frozen_top"] = json.loads(
            pathlib.Path(a.brief).read_text())["mechanisms"][0]["id"]
        report["top_agrees"] = report["draft_top"] == report["frozen_top"]

    (out_dir / f"setup-report-{res['request_hash'][:16]}.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(f"setup {res['source']}: overlap={report['overlap']} "
          f"null={'PASS' if report['null_test_pass'] else 'FAIL'} "
          f"top_agrees={report.get('top_agrees')}")
    satisfied = bool(draft and not errors and report["null_test_pass"])
    if a.traces_db is not None:
        import sqlite3 as _sq
        from store import db as _db
        con = _sq.connect(a.traces_db)
        try:
            con.executescript(_db.SCHEMA)
            _db.add_trace(
                con, a.traces_label or inputs.name, "setup_draft", 0,
                res["request_hash"],
                hashlib.sha256(res["text"].encode()).hexdigest(),
                list(errors), "satisfied" if satisfied else "failed_checks",
                len(res["text"]))
            con.commit()
        finally:
            con.close()
    return 0 if satisfied else 1


if __name__ == "__main__":
    raise SystemExit(main())
