"use client";

import { useEffect, useState } from "react";
import { getDemo2Nepal } from "../../../../lib/api";

export default function NepalMemoryDemo() {
  const [brief, setBrief] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDemo2Nepal()
      .then((b) => setBrief(b))
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  if (error) return <main className="demo"><p className="meta">{error}</p></main>;
  if (!brief) return <main className="demo"><p className="meta">Loading demo…</p></main>;

  const d = brief.data;
  const id = d.identity;

  return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · the system&apos;s memory <span className="mode">{brief.mode}</span></p>
        <h1>Why this desk is empty — and why that is the point</h1>
        <p className="lede">
          BlindSpot studied the Nepal floods and gave its verdict: {d.frozen.top_title}, with a
          support score of {(d.frozen.probability * 100).toFixed(1)} out of 100. That answer is locked.
          Memory — learning from replays of the past, the way the fire study does — holds{" "}
          <strong>{d.memory_status.episodes} episodes</strong> here: {d.memory_status.note}. An empty
          desk with the reason written on it is worth more than a full one built on sand.
        </p>
      </header>

      <section>
        <h2>The locked verdict</h2>
        <p>{d.frozen.verdict}</p>
      </section>

      <section>
        <h2>Why no replays exist</h2>
        <p>
          Memory learns by rewinding: pick a date, cover up everything after it, conclude from
          only what came before, then check what actually happened. That needs observations spread
          across many dates. The flood records do not have them: the curated inputs carry no dates
          at all, and across all three dated flood exports only{" "}
          <strong>{d.why_empty.dated_damage_days} real damage days</strong> exist, against{" "}
          <strong>{d.why_empty.dateless_features.toLocaleString()} features with no date</strong>.{" "}
          {d.why_empty.note} Two snapshots cannot teach anything — and the system says so instead
          of pretending.
        </p>
        <p className="meta">Checked, not assumed: every export read, every date counted.</p>
      </section>

      <section>
        <h2>What is proven here instead</h2>
        <p>
          With no memory installed, the Nepal brief must come out letter-for-letter identical to
          the frozen one. Both fingerprints:
        </p>
        <table className="kv"><tbody>
          <tr><td>Frozen brief</td><td>{id.frozen_brief_sha256.slice(0, 16)}…</td></tr>
          <tr><td>Memory-empty brief</td><td>{id.memory_empty_brief_sha256.slice(0, 16)}…</td></tr>
          <tr><td>Identical</td><td>{id.match ? "Yes — silence verified, not promised." : "NO — investigate."}</td></tr>
        </tbody></table>
      </section>

      <section>
        <h2>What would unlock this desk</h2>
        <ol className="steps">
          {d.unlock.map((u) => (
            <li key={u}><p>{u}</p></li>
          ))}
        </ol>
        <p>
          The machinery already works on any study&apos;s evidence — it waits on dated observations,
          which no analysis can manufacture. Until then, this page stands as proof that the system
          would rather show you an empty desk than a made-up one.
        </p>
      </section>

      <section>
        <h2>Back to the study</h2>
        <p><a href="/demo/nepal-cascade">The frozen Nepal cascade brief</a> <span className="meta">— verdict, evidence, maps, and conclusions, unchanged.</span></p>
      </section>
    </main>
  );
}
