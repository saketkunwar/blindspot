"use client";

import { useEffect, useState } from "react";
import MapPane, { legendOf } from "../../../components/MapPane";
import { getDemoFire, getDemoFireGeo } from "../../../lib/api";

const STEPS = [
  { k: "Detect", d: "FIRMS detections gridded into cells over five pre-cutoff days; hotspot cells tagged at the noise floor." },
  { k: "Classify", d: "Ledger of evidence facts scored against an open mechanism set that includes a cessation story." },
  { k: "Cascade", d: "Scores normalize to support-strength probabilities; the verification gate admits only ledger-grounded claims." },
];

export default function FireStudyDemo() {
  const [brief, setBrief] = useState(null);
  const [geo, setGeo] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getDemoFire(), getDemoFireGeo()])
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
    { n: counts.detections.toLocaleString(), l: "pre-cutoff FIRMS detections" },
    { n: String(counts.cells), l: "grid cells with fire" },
    { n: String(d.mechanisms.length), l: "candidate mechanisms" },
    { n: String(d.prompt_audit.violations.length), l: "prompt-audit violations" },
  ];

  return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · pre-cutoff autoinsight <span className="mode">{brief.mode}</span></p>
        <h1>Peatland fires: what the pre-cutoff evidence supports</h1>
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
            {geo ? `${geo.data.cell_count} cells · ${geo.data.detections.toLocaleString()} detections` : "loading layers…"}
          </span>
        </div>
        <div className="mapwrap">
          <MapPane layers={layers} />
        </div>
      </section>

      <section>
        <h2>Why this can be trusted</h2>
        <p className="lede">The deterministic core (QSTR)</p>
        <p>Every number here comes from the same deterministic fact catalog that powers the flood study — counting, clustering, and time-gap statistics as pure functions over frozen inputs. Run it twice and every fact value, every score, every probability is identical; run it on half the map and the ranking does not move. There is no sampling step anywhere between the detections and the verdict, so nothing in the result depends on chance, and everything in it can be recomputed by hand from the pinned files.</p>
        <p className="lede">The model&apos;s role (setup round)</p>
        <p>The language model proposed six fire mechanisms with its own weights from the pre-cutoff ledger alone — and independently put the most weight on the same two lead facts the frozen brief leans on, while disagreeing on top. That split is the whole design: the model brings framing, the frozen human weights bring conviction, and the ledger arithmetic decides. The proposal passed the null test and a clean prompt audit; had it failed either, no brief would exist.</p>
      </section>

      <section>
        <h2>Conclusion</h2>
        <p className="lede">What was studied</p>
        <p>What a mid-September 2026 peatland fire episode in Kalimantan really was: one spreading event, a contained burn, a full cessation — or suppression followed by peat restart. The evidence is 6,142 FIRMS detections over five days across 30 grid cells, 28 of them hot at the noise floor.</p>
        <p className="lede">How it was studied</p>
        <p>The same pipeline shape as the flood study, with no flood code executing: detections gridded into dated cells, human-authored rules with weights locked before compute, and a rules-driven builder scoring six facts into four mechanisms. Two independent holdouts carry the claim — every detection after September 20 locked away (the brief had to predict the restart unseen), and the eastern half of the map masked out (the ranking had to survive half its data). A live setup round then drafted its own mechanisms from the pre-cutoff ledger alone.</p>
        <p className="lede">Insights learned</p>
        <p>Suppression-then-restart wins at 0.84 against 0.11 for continued spread: a clean multi-day gap followed by an unbroken burn run already favors it, and the held-out days confirm it. The spatial holdout kept the identical ranking on half the map — the signal is pervasive, not one hotspot&apos;s doing. The setup round independently weighted the same two lead facts highest while disagreeing on top, which is exactly what framing without conviction looks like. And the study paid for itself in engine improvements — scoped cluster counting, a time-scale divisor, weights inside fact entries — each proven generic by the flood brief staying byte-identical throughout.</p>
      </section>
    </main>
  );
}
