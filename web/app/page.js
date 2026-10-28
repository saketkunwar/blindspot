"use client";

import { useEffect, useMemo, useState } from "react";
import MapPane from "../components/MapPane";
import { getFire, getFlood } from "../lib/api";

export default function Console() {
  const [flood, setFlood] = useState(null);
  const [fire, setFire] = useState(null);
  const [sel, setSel] = useState(null); // {kind, id}
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getFlood(), getFire()])
      .then(([fl, fi]) => { setFlood(fl); setFire(fi); })
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  const floodFeats = flood?.data.act1.features ?? [];
  const layers = useMemo(() => {
    if (!flood || !sel) return [];
    if (sel.kind === "band") {
      const key = sel.id === "may_be" ? "may_be" : "must_be";
      return [{ type: "Feature", properties: { name: key }, geometry: flood.data.act2[key] }];
    }
    return [];
  }, [flood, sel]);

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
        {flood && <p>{flood.data.scenario} <span className="mode">{flood.mode}</span></p>}
        {fire && <p>{fire.data.scenario} <span className="mode">{fire.mode}</span></p>}
        <h2>Bands</h2>
        {["may_be", "must_be"].map((b) => (
          <button key={b} className={sel?.id === b ? "item active" : "item"}
            onClick={() => setSel({ kind: "band", id: b })}>{b}</button>
        ))}
        <h2>Features ({floodFeats.length})</h2>
        {floodFeats.slice(0, 200).map((f) => (
          <button key={f.id} className={sel?.id === f.id ? "item active" : "item"}
            onClick={() => setSel({ kind: "feature", id: f.id })}>
            {f.id} <span className="meta">{f.fwd.rcc8.relation} · {f.fwd.band}</span>
          </button>
        ))}
        <h2>Claims</h2>
        {(fire?.data.claims ?? []).map((c) => (
          <button key={c.id} className={sel?.id === c.id ? "item active" : "item"}
            onClick={() => setSel({ kind: "claim", id: c.id })}>
            {c.id} <span className="meta">{c.verdict}</span>
          </button>
        ))}
      </div>
      <div className="pane-map"><MapPane layers={layers} /></div>
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
          </tbody></table>
        )}
        {detail?.verdict && (
          <table className="kv"><tbody>
            <tr><td>verdict</td><td>{detail.verdict}</td></tr>
            <tr><td>interval</td><td>{detail.start} to {detail.end}</td></tr>
          </tbody></table>
        )}
      </div>
    </div>
  );
}
