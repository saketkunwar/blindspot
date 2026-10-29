"use client";

import { useEffect, useMemo, useState } from "react";
import MapPane, { legendOf } from "../components/MapPane";
import { getFire, getFlood } from "../lib/api";

export default function Console() {
  const [flood, setFlood] = useState(null);
  const [fire, setFire] = useState(null);
  const [sel, setSel] = useState({ kind: "band", id: "may_be" }); // {kind, id}
  const [error, setError] = useState("");
  const [show, setShow] = useState("flood"); // scenario filter: flood | fire
  const [layer, setLayer] = useState("all"); // feature layer filter
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    Promise.all([getFlood(), getFire()])
      .then(([fl, fi]) => { setFlood(fl); setFire(fi); })
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  const floodFeats = flood?.data.act1.features ?? [];
  const layersPresent = [...new Set(floodFeats.map((f) => f.layer))];
  const visibleFeats = floodFeats.filter((f) => layer === "all" || f.layer === layer);
  const inMayBe = useMemo(() => new Set(
    (flood?.data.act2.assets_in_may_be ?? []).map((a) => a.id)), [flood]);
  const fireCells = useMemo(() => {
    if (!fire) return [];
    const g = fire.data.grid_deg;
    return (fire.data.cells ?? []).map((c) => {
      const [lon, lat] = c.origin;
      return {
        type: "Feature", properties: { kind: "fire cell", id: c.id },
        geometry: { type: "Polygon", coordinates: [[
          [lon, lat], [lon + g, lat], [lon + g, lat + g], [lon, lat + g], [lon, lat]]] },
      };
    });
  }, [fire]);
  const bandOf = (key) => {
    // must_be is a GeometryCollection: flatten members so every layer
    // filter and fitBounds sees plain geometries.
    const flat = (geom) => geom?.type === "GeometryCollection"
      ? (geom.geometries ?? []).flatMap(flat) : [geom];
    return flat(flood.data.act2[key])
      .filter((g) => g && g.type)
      .map((geometry, i) => ({ type: "Feature",
        properties: { name: key, part: i }, geometry }));
  };
  const layers = useMemo(() => {
    if (!flood || !sel) return [];
    // Act-1 features carry no geometry; show the blind-spot band they are
    // assessed against. Claims show the fire grid (cell boxes from origin).
    if (sel.kind === "band") return bandOf(sel.id === "may_be" ? "may_be" : "must_be");
    if (sel.kind === "feature") return bandOf("may_be");
    if (sel.kind === "claim") return fireCells;
    return [];
  }, [flood, sel, fireCells]);

  const detail = useMemo(() => {
    if (!flood || !sel) return null;
    if (sel.kind === "feature") return floodFeats.find((f) => f.id === sel.id) ?? null;
    if (sel.kind === "claim") return fire?.data.claims.find((c) => c.id === sel.id) ?? null;
    return null;
  }, [flood, fire, sel, floodFeats]);

  return (
    <div className="console">
      <div className="pane pane-left">
        <h2>Scenarios</h2>
        {error && <p className="meta">{error}</p>}
        {!flood && !error && <p className="meta">Loading scenarios…</p>}
        {flood && (
          <button className={show === "flood" ? "item active" : "item"}
            onClick={() => setShow("flood")}>
            {flood.data.scenario} <span className="mode">{flood.mode}</span>
          </button>
        )}
        {fire && (
          <button className={show === "fire" ? "item active" : "item"}
            onClick={() => setShow("fire")}>
            {fire.data.scenario} <span className="mode">{fire.mode}</span>
          </button>
        )}
        {show === "flood" && (<>
        <h2>Bands</h2>
        {["may_be", "must_be"].map((b) => (
          <button key={b} className={sel?.id === b ? "item active" : "item"}
            onClick={() => setSel({ kind: "band", id: b })}>{b}</button>
        ))}
        <h2>Features ({visibleFeats.length} of {floodFeats.length})</h2>
        <p className="meta">
          {["all", ...layersPresent].map((l, i) => (
            <span key={l}>
              {i > 0 && " · "}
              <button className="linklike" onClick={() => { setLayer(l); setLimit(50); }}>
                {layer === l ? <strong>{l}</strong> : l}
              </button>
            </span>
          ))}
        </p>
        {visibleFeats.slice(0, limit).map((f) => (
          <button key={f.id} className={sel?.id === f.id ? "item active" : "item"}
            onClick={() => setSel({ kind: "feature", id: f.id })}>
            {f.id} <span className="meta">{f.fwd.rcc8.relation} · {f.fwd.band}</span>
          </button>
        ))}
        {visibleFeats.length > limit && (
          <button className="item" onClick={() => setLimit((n) => n + 50)}>
            Show more ({visibleFeats.length - limit} remaining)
          </button>
        )}
        </>)}
        {show === "fire" && (<>
        <h2>Claims</h2>
        {(fire?.data.claims ?? []).map((c) => (
          <button key={c.id} className={sel?.id === c.id ? "item active" : "item"}
            onClick={() => setSel({ kind: "claim", id: c.id })}>
            {c.id} <span className="meta">{c.verdict}</span>
          </button>
        ))}
        </>)}
      </div>
      <div className="pane-map">
        <div className="map-legend">
          {legendOf(layers).map(([kind, color]) => (
            <span className="legend-chip" key={kind}>
              <span className="swatch" style={{ background: color }} />{kind}
            </span>
          ))}
        </div>
        <MapPane layers={layers} />
      </div>
      <div className="pane pane-right">
        <h2>Detail</h2>
        {!detail && <p className="meta">Select a feature, band, or claim.</p>}
        {detail?.fwd && (
          <table className="kv"><tbody>
            <tr><td>relation</td><td>{detail.fwd.rcc8.relation} ({detail.fwd.rcc8.status})</td></tr>
            <tr><td>rectangle</td><td>{detail.fwd.rectangle.join(", ")}</td></tr>
            <tr><td>tiles</td><td>{detail.fwd.tiles.join(" ")}</td></tr>
            <tr><td>gap / centroid</td><td>{detail.fwd.edge_gap_m.toFixed(1)} m / {detail.fwd.centroid_dist_km.toFixed(2)} km</td></tr>
            <tr><td>band</td><td>{detail.fwd.band}</td></tr>
            <tr><td>split alert</td><td>{String(detail.split_alert)}</td></tr>
            <tr><td>may_be</td><td>{inMayBe.has(detail.id) ? "inside" : "outside"}</td></tr>
          </tbody></table>
        )}
        {detail?.verdict && (
          <table className="kv"><tbody>
            <tr><td>verdict</td><td>{detail.verdict}</td></tr>
            <tr><td>interval</td><td>{detail.start} to {detail.end}</td></tr>
            {(detail.evidence ?? []).map((e, i) => (
              <tr key={i}><td>evidence {i + 1}</td><td>{(e.overlap_days ?? []).join(", ") || "—"}</td></tr>
            ))}
          </tbody></table>
        )}
      </div>
    </div>
  );
}
