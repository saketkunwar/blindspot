"use client";

import { useEffect, useState } from "react";
import MapPane from "../../../components/MapPane";
import { getDemoNepal, getDemoNepalGeo } from "../../../lib/api";

const STEPS = [
  { k: "Detect", d: "Per-snapshot kernel pass over pre-cutoff damage: reach split, channel adjacency, tributary-cluster rule." },
  { k: "Classify", d: "Ledger of evidence facts scored against an open mechanism set that includes nothing-happens." },
  { k: "Cascade", d: "Scores normalize to support-strength probabilities; the verification gate admits only ledger-grounded claims." },
];

export default function NepalCascadeDemo() {
  const [brief, setBrief] = useState(null);
  const [geo, setGeo] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getDemoNepal(), getDemoNepalGeo()])
      .then(([b, g]) => { setBrief(b); setGeo(g); })
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  if (error) return <main className="demo"><p className="meta">{error}</p></main>;
  if (!brief) return <main className="demo"><p className="meta">Loading demo…</p></main>;

  const d = brief.data;
  const facts = Object.entries(d.ledger.facts);
  return (
    <main className="demo">
      <header className="hero">
        <p className="meta">BlindSpot demo · pre-cutoff autoinsight <span className="mode">{brief.mode}</span></p>
        <h1>Valley survey: what the pre-cutoff evidence supports</h1>
        <p className="lede">{d.verdict}</p>
        <p className="meta">{d.probability_semantics} · snapshot {d.as_of_label}</p>
      </header>

      <section>
        <h2>Evidence cards</h2>
        <div className="cards">
          {facts.map(([fid, f]) => (
            <div className="card" key={fid}>
              <p className="meta">{fid}</p>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>How it works</h2>
        <div className="cards">
          {STEPS.map((s) => (
            <div className="card" key={s.k}>
              <p><strong>{s.k}</strong></p>
              <p className="meta">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>Mechanism ranking</h2>
        {d.mechanisms.map((m) => (
          <div className="bar-row" key={m.id}>
            <span className="bar-label">{m.title}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(m.probability * 100).toFixed(1)}%` }} />
            </span>
            <span className="bar-num">{(m.probability * 100).toFixed(1)}%</span>
          </div>
        ))}
      </section>

      <section>
        <h2>Findings</h2>
        <table className="kv">
          <tbody>
            <tr><td>Cluster finding</td><td>{d.cluster_finding}</td></tr>
            <tr><td>Model round</td><td>{d.model_round.status}{d.model_round.reason ? ` — ${d.model_round.reason}` : ""} · model {d.model_round.model}</td></tr>
            <tr><td>Prompt audit</td><td>{d.prompt_audit.forbidden_tokens_checked} input-derived tokens checked, {d.prompt_audit.violations.length} violations</td></tr>
            <tr><td>Pre-cutoff features</td><td>{d.inputs_audit.counts.kept_pre_cutoff} of {d.inputs_audit.counts.cascade_total} surveyed</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Legend map</h2>
        <p className="meta">
          {geo ? `target reach · observed outline · pre-cutoff damage sample (${geo.data.layers.length} drawn of ${geo.data.pre_cutoff_total}, cap ${geo.data.sample_cap})` : "loading layers…"}
        </p>
        <div className="mapwrap">
          <MapPane layers={geo ? geo.data.layers : []} />
        </div>
      </section>
    </main>
  );
}
