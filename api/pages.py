"""Server-rendered study pages (P1 presentation), data only, stdlib only.

Every string and number on the page comes from the frozen brief, the
curated geo inputs, or the gt check — names and values are html-escaped,
and there is no filler copy. The map is a schematic SVG scaled from the
real extent box and target-reach coordinates (labelled as such); the
interactive map stays in the web console.
"""
from __future__ import annotations

import html

CSS = """
body{font-family:sans-serif;max-width:56rem;margin:2rem auto;padding:0 1rem;color:#222}
.hero{border:1px solid #999;padding:1rem 1.25rem}
.badge{display:inline-block;border:1px solid #666;padding:0 .5rem;font-size:.85rem}
.bar{height:1em;background:#333}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #bbb;padding:.35rem .6rem;text-align:left}
svg.map{border:1px solid #999;width:100%;height:auto}
@media print{.noprint{display:none}body{margin:0;max-width:none}.hero{border-width:2px}}
"""


def _schematic_svg(extent_bbox, target_features) -> str:
    x0, y0, x1, y1 = (float(v) for v in extent_bbox)
    w, h = 600.0, 300.0
    sx = w / (x1 - x0) if x1 != x0 else 1.0
    sy = h / (y1 - y0) if y1 != y0 else 1.0

    def pt(lon, lat) -> str:
        return f"{(lon - x0) * sx:.1f},{h - (lat - y0) * sy:.1f}"

    lines = []
    for f in target_features:
        g = (f.get("geometry") or {})
        if g.get("type") == "LineString":
            coords = g.get("coordinates", [])
            if len(coords) >= 2:
                lines.append('<polyline points="' + " ".join(
                    pt(*c[:2]) for c in coords) + '" fill="none" stroke-width="2"/>')
    reach = "".join(f'<g stroke="#000">{ln}</g>' for ln in lines)
    return (f'<svg class="map" viewBox="0 0 {w:.0f} {h:.0f}" role="img">'
            f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="none" stroke-width="2"/>'
            f"{reach}</svg>"
            "<p>Schematic: observed outline box plus target reach, scaled from curated inputs.</p>")


def render_study_page(study_id: str, brief: dict, extent: dict,
                      target_features: list, pre_total: int,
                      gt: dict | None) -> str:
    e = html.escape
    top = brief["mechanisms"][0]
    mechs = "".join(
        f'<tr><td>{e(m["id"])}</td><td>{e(m.get("title", ""))}</td>'
        f'<td>{m["probability"]:.4f}</td>'
        f'<td><div class="bar" style="width:{100 * m["probability"]:.1f}%"></div></td></tr>'
        for m in brief["mechanisms"])
    facts = "".join(f"<li><b>{e(fid)}</b>: {e(f['text'])}</li>"
                    for fid, f in brief["ledger"]["facts"].items())
    audit = brief.get("inputs_audit", {})
    counts = audit.get("counts", {})
    if gt is None:
        gt_block = "<p>No gt check recorded yet (post-freeze artifact).</p>"
    else:
        gv = e(str(gt.get("verdict", "")))
        gr = e(str(gt.get("true_outcome_rank", "")))
        gt_block = "<p>GT check: " + gv + " (true-outcome rank: " + gr + ")</p>"
    kept = e(str(counts.get("kept_pre_cutoff", pre_total)))
    total = e(str(counts.get("cascade_total", "")))
    n_target = e(str(len(target_features)))
    verdict = e(str(brief.get("verdict", "")))
    top_id = e(str(top.get("id", "")))
    top_title = e(str(top.get("title", "")))
    top_p = "%.4f" % float(top["probability"])
    snapshot = e(str(brief.get("as_of_label", "")))
    cluster = e(str(brief.get("cluster_finding", "")))
    sid = e(study_id)
    return (f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>BlindSpot study {sid}</title><style>{CSS}</style></head>
<body>
<div class="hero"><h1>Study {sid}</h1>
<p>{verdict}</p>
<p>Top story: <b>{top_id}</b> \u2014 {top_title} """
    f"""(support {top_p}). Snapshot {snapshot}."""
    f""" <span class="badge">cached</span></p></div>
<h2>Evidence</h2><ul>{facts}</ul>
<h2>How it works</h2><ol>
<li>Detect: per-feature relations against the static outline, pre-cutoff only.</li>
<li>Classify: ledger facts activate against frozen thresholds.</li>
<li>Cascade: mechanisms score from active facts; probabilities are support strengths.</li></ol>
<h2>Mechanism ranking</h2>
<table><tr><th>id</th><th>title</th><th>support</th><th></th></tr>{mechs}</table>
<h2>Findings</h2>
<p>Cluster: {cluster}</p>
<p>Pre-cutoff damage: {kept} of """
    f"""{total} features; """
    f"""{n_target} target-reach pieces.</p>
{gt_block}
<h2>Map data</h2>{_schematic_svg(extent["bbox"], target_features)}
<p class="noprint">Raw layers: <a href="../geo">geo JSON</a> \u00b7 """
    f"""brief: <a href="brief">brief JSON</a></p>
</body></html>""")
