"use client";

import { useEffect, useState } from "react";
import MapPane, { legendOf } from "../../../components/MapPane";
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
  const layers = geo ? geo.data.layers : [];
  const counts = d.inputs_audit.counts;
  const counters = [
    { n: counts.kept_pre_cutoff.toLocaleString(), l: "pre-cutoff damage features" },
    { n: counts.cascade_total.toLocaleString(), l: "features surveyed" },
    { n: String(d.mechanisms.length), l: "candidate mechanisms" },
    { n: String(d.prompt_audit.violations.length), l: "prompt-audit violations" },
  ];

  return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · pre-cutoff autoinsight <span className="mode">{brief.mode}</span></p>
        <h1>Valley survey: what the pre-cutoff evidence supports</h1>
        <p className="lede">{d.verdict}</p>
        <p className="meta">{d.probability_semantics} · snapshot {d.as_of_label}</p>
      </header>

      <section>
        <h2>Survey findings</h2>
        <div className="counters">
          {counters.map((c) => (
            <div className="counter" key={c.l}>
              <p className="counter-num">{c.n}</p>
              <p className="meta">{c.l}</p>
            </div>
          ))}
        </div>
        <table className="kv"><tbody>
          <tr><td>Cluster finding</td><td>{d.cluster_finding}</td></tr>
          <tr><td>Model round</td><td>{d.model_round.status}{d.model_round.reason ? ` — ${d.model_round.reason}` : ""} · model {d.model_round.model}</td></tr>
        </tbody></table>
      </section>

      <section>
        <h2>Evidence</h2>
        <div className="cards">
          {facts.map(([fid, f]) => (
            <div className={"card" + (f.active ? "" : " quiet")} key={fid}>
              <p className="meta">{fid}{f.active ? "" : " · quiet"}</p>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>How it works</h2>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.k}><p><strong>{s.k}</strong></p><p className="meta">{s.d}</p></li>
          ))}
        </ol>
      </section>

      <section>
        <h2>Mechanism ranking</h2>
        {d.mechanisms.map((m, i) => (
          <div className="bar-row" key={m.id}>
            <span className="bar-rank">{i + 1}</span>
            <span className="bar-label">{m.title}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(m.probability * 100).toFixed(1)}%` }} />
            </span>
            <span className="bar-num">{(m.probability * 100).toFixed(1)}%</span>
          </div>
        ))}
      </section>

      <section>
        <h2>Legend map</h2>
        <div className="legend">
          {legendOf(layers).map(([kind, color]) => (
            <span className="legend-chip" key={kind}>
              <span className="swatch" style={{ background: color }} />{kind}
            </span>
          ))}
          <span className="meta legend-note">
            {geo ? `${layers.length} drawn of ${geo.data.pre_cutoff_total}, cap ${geo.data.sample_cap}` : "loading layers…"}
          </span>
        </div>
        <div className="mapwrap">
          <MapPane layers={layers} />
        </div>
      </section>
    </main>
  );
}
