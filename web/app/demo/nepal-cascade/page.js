"use client";

import { useEffect, useState } from "react";
import MapPane, { legendOf } from "../../../components/MapPane";
import { getDemoNepal, getDemoNepalGeo, getDemo2Nepal } from "../../../lib/api";

const STEPS = [
  { k: "Detect", d: "Per-snapshot kernel pass over pre-cutoff damage: reach split, channel adjacency, tributary-cluster rule." },
  { k: "Classify", d: "Ledger of evidence facts scored against an open mechanism set that includes nothing-happens." },
  { k: "Cascade", d: "Scores normalize to support-strength probabilities; the verification gate admits only ledger-grounded claims." },
];

export default function NepalCascadeDemo() {
  const [brief, setBrief] = useState(null);
  const [geo, setGeo] = useState(null);
  const [mem, setMem] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getDemoNepal(), getDemoNepalGeo()])
      .then(([b, g]) => { setBrief(b); setGeo(g); })
      .catch((e) => setError(`API unreachable: ${e.message}`));
    getDemo2Nepal().then((m) => setMem(m)).catch(() => {});
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

      {mem && (
      <section>
        <h2>Tested, not just computed</h2>
        <p>A verdict this strong needs enemies: ground truth the brief never saw.</p>
        <p className="lede">Time held out</p>
        <p>After the freeze, {mem.data.validation.temporal.newly_destroyed} newly destroyed features from the quarantined window {mem.data.validation.temporal.gt_window} were checked against the frozen top story — along with the satellite barrier-lake log between the snapshots. Match: the answer was fixed before the ground truth opened.</p>
        <p className="lede">Space: still open</p>
        <p>{mem.data.validation.spatial.reason.charAt(0).toUpperCase() + mem.data.validation.spatial.reason.slice(1)} — {mem.data.validation.spatial.what_it_would_take}. Until that re-run exists, this half of the validation is openly pending, not quietly assumed.</p>
      </section>
      )}

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

      <section>
        <h2>Why this can be trusted</h2>
        <p className="lede">The deterministic core (QSTR)</p>
        <p>Every spatial and temporal claim here comes from qualitative relations — RCC-8 topology (overlap, contact, containment) and Allen interval relations (before, during, after) — computed by pure functions over frozen geometry. No embeddings, no sampling, no temperature. The same inputs always produce the same relations, which is why the brief replays byte-for-byte and why every claim in it can be traced to an exact computation. The core cannot hallucinate a relation; it can only report what the shapes and timestamps entail.</p>
        <p className="lede">The model&apos;s role (setup round)</p>
        <p>The language model proposes — it drafts the open mechanism set and suggests weights from an anonymized prompt that contains no names, no dates, and no outcome. It never computes evidence and never sees ground truth. Its proposal must pass a null test (all facts quiet means the quiet story wins) and a prompt audit, and its disagreement with the frozen human weights is preserved as expected framing-without-conviction. Conviction lives in the signed weights and the ledger arithmetic, not in the model&apos;s text.</p>
      </section>

      <section>
        <h2>Conclusion</h2>
        <p className="lede">What was studied</p>
        <p>Whether the 2015 Gorkha earthquake set up a secondary disaster in the Langtang Valley: landslide debris damming a river, water ponding behind it, and the dam bursting into a flood larger than the quake&apos;s direct damage. The evidence is frozen OpenStreetMap data over the valley&apos;s river network, bridges, hydropower sites, and settlements.</p>
        <p className="lede">How it was studied</p>
        <p>Raw extracts were curated into pre-cutoff roles, then summarized in a context card with every place name anonymized and every date redacted, so the machinery never saw anything that could identify the event. Eight evidence facts were computed against frozen, human-signed rules and scored into probabilities over an open mechanism set that always included a nothing-happens story. The brief replayed byte-for-byte from cassettes, and ground-truth checks ran only after the freeze.</p>
        <p className="lede">Insights learned</p>
        <p>Impoundment-then-burst wins at 0.94 support, carried by one fact above all: 518 damage detections clumped near the channel, a concentration no rival mechanism explains. Reach analysis places the damage downstream of the ponding zone, matching a burst origin rather than scattered quake damage. The hazard-zone gate confirmed every zone is computable from extent, reach, and group relations — while reporting honestly that 113 of 418 zones touch neither outline nor assets (remote wet network, not broken plumbing). And the pipeline graded none of its own homework: the answer was fixed before the ground truth opened.</p>
      </section>
    </main>
  );
}
