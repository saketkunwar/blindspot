"use client";

import { useEffect, useState } from "react";
import { getDemo2CrossRegion } from "../../../../lib/api";

export default function CrossRegionDemo() {
  const [snap, setSnap] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDemo2CrossRegion()
      .then((b) => setSnap(b))
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  if (error) return <main className="demo"><p className="meta">{error}</p></main>;
  if (!snap) return <main className="demo"><p className="meta">Loading demo…</p></main>;

  const d = snap.data;
  const lead = d.top_patterns[0];

  return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · does fire rhyme across continents <span className="mode">{snap.mode}</span></p>
        <h1>One key, eleven firegrounds, {d.patterns} shapes</h1>
        <p className="lede">
          Most systems interpolate what was seen. BlindSpot reasons about what was not seen —
          and this page asks the harder question: does the same hidden shape appear in fires
          that never met each other?
        </p>
        <p>
          Eleven regions on five continents — Kalimantan peat, Amazon rainforest, Cerrado
          savanna, Iberian scrub, Texas brush, Chaco, Mozambique, Zambia, northern Australia,
          the western US, Attica — were each slid day by day through the frozen rules: predict
          from everything before a cutoff, label from everything after, under one frozen
          outcome rule and one frozen pattern key. {d.episodes} past episodes resulted,{" "}
          {d.labelled} with known outcomes, grouping into {d.patterns} distinct shapes.
        </p>
      </header>

      <section>
        <h2>Why this matters to an operator</h2>
        <p>
          A pattern that repeats only in one valley is local lore. A pattern that repeats in
          Iberia and Texas — different continents, different fuels, same shape — is evidence
          that the frozen rules carve nature at a joint, not at a coincidence. And the
          opposite outcome carries equal weight: if new data breaks these groups apart, the
          honest finding is that fire patterns are regional, and the bar must be earned
          region by region. Both readings are reported as-is; the key and the rule stay frozen
          either way.
        </p>
      </section>

      <section>
        <h2>Where the count stands</h2>
        <p>
          The leading shape holds {lead.labelled} labelled cases of the {d.speak_bar} the bar
          requires — {lead.episodes} episodes across {Object.keys(lead.scenes).join(", ")}{" "}
          — {lead.labelled >= d.speak_bar
            ? "the bar is met: memory speaks, three continents in one shape."
            : "one case short of letting memory speak."} The runner-up stands at{" "}
          {d.top_patterns[1].labelled} of {d.speak_bar}.
        </p>
        <table className="kv"><tbody>
          {d.top_patterns.map((p, i) => (
            <tr key={i}>
              <td>Shape {i + 1}</td>
              <td>{p.labelled} labelled / {p.episodes} episodes — {Object.entries(p.scenes).map(([s, n]) => `${s} ×${n}`).join(", ")}</td>
            </tr>
          ))}
        </tbody></table>
        <p className="meta">{d.cross_scene} of {d.patterns} shapes span more than one region. Recomputed from the memory store under the frozen key — the generator refuses to hand-type a single relation.</p>
      </section>

      <section>
        <h2>The eleven firegrounds</h2>
        <table className="kv"><tbody>
          {d.scenes.map((s) => (
            <tr key={s.scene}>
              <td>{s.scene}</td>
              <td>{s.episodes} episodes, {s.labelled} labelled</td>
            </tr>
          ))}
        </tbody></table>
      </section>

      <section>
        <h2>What comes next — the three pulls</h2>
        <p>
          The diagnosis this page is built on said the highest-value data in the world is
          narrow: extend the Iberian and Texan windows and fetch one quiet window for a
          matched box (the labelling rule&apos;s arm that has never fired). No new regions —
          different fuels add patterns of one, and the key is strict on purpose. Those three
          pulls have now landed — statuses below — and the count above is what they chose.
          The August window burned, so the quiet arm stays missing; that absence is reported,
          not hidden.
        </p>
        <table className="kv"><tbody>
          <tr><td>Iberia extension</td><td>{d.pending_pulls.iberia_ext} — five September–October days over the Iberian box</td></tr>
          <tr><td>Texas extension</td><td>{d.pending_pulls.texas_ext} — five days over the Texas box</td></tr>
          <tr><td>Quiet window</td><td>{d.pending_pulls.quiet} — an August Kalimantan window, read as-is whether it burns or not</td></tr>
        </tbody></table>
        <p className="meta">When the pulls land they are curated into pinned scenes and backfilled through the agent path; this page then refreshes. Three readings are possible — the fifth label (memory speaks), a pattern break (regionality proven), a first quiet (the missing arm exercised) — and all three ship as-is.</p>
      </section>

      <section>
        <h2>How to check this by hand</h2>
        <p>Run <span className="meta">python scripts/make_crossregion.py</span> — it re-reads the memory store, recomputes every group under the frozen key, checks the raw directory for the pending pulls, and refuses to write unless the file parses back identically. Provenance fingerprints travel inside the snapshot.</p>
      </section>
    </main>
  );
}
