"use client";

import { useEffect, useState } from "react";
import { getDemo2Chain } from "../../../../lib/api";

const REL = {
  NTPP: "properly inside, touching nothing — like a coin in a closed box",
  NTPPi: "properly containing — the box around that coin",
  TPP: "inside and touching the edge — like a sticker on the inside of the lid",
  EC: "touching at the edge but not overlapping — like two pages pressed together",
  DC: "fully separate — no contact at all",
  PO: "partly overlapping — like two crossed planks",
};

export default function ChainDemo() {
  const [snap, setSnap] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDemo2Chain()
      .then((b) => setSnap(b))
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  if (error) return <main className="demo demo-flood"><p className="meta">{error}</p></main>;
  if (!snap) return <main className="demo demo-flood"><p className="meta">Loading demo…</p></main>;

  const d = snap.data;
  const c = d.composition;

  return (
    <main className="demo demo-flood">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · the algebra, hop by hop <span className="mode">{snap.mode}</span></p>
        <h1>One bridge, four hops, one forced answer</h1>
        <p className="lede">
          The question is {d.question} The system answers it the way you would
          give directions: not with coordinates, but with relationships — this
          lies inside that, that touches this — chained until the answer is
          forced. Every hop below is a real computation from the frozen flood
          study, shown with the relation the machine actually derived.
        </p>
        <p className="meta">Subject: {d.subject} · nothing here is illustrated; every value replays from pinned files</p>
      </header>

      {d.hops.map((h) => (
        <section key={h.n}>
          <h2>Hop {h.n}: {h.a} → {h.b}</h2>
          <p>{h.says}.</p>
          {h.fwd ? (
            <table className="kv"><tbody>
              <tr><td>Forward</td><td>{h.fwd.rcc8} — {REL[h.fwd.rcc8] || h.fwd.rcc8}</td></tr>
              <tr><td>Backward</td><td>{h.inv.rcc8} — the exact converse, checked on every pair, {REL[h.inv.rcc8] || ""}</td></tr>
              <tr><td>Extents</td><td>rectangle pair [{h.fwd.rectangle.join(", ")}], touching tiles {h.fwd.tiles.join(", ")}, bearing {h.fwd.bearing}</td></tr>
              <tr><td>Distance</td><td>edge gap {Number(h.fwd.edge_gap_m).toFixed(1)} m, centres {Number(h.fwd.centroid_dist_km).toFixed(1)} km apart — band {h.fwd.band}</td></tr>
              <tr><td>Source</td><td>{h.source}</td></tr>
            </tbody></table>
          ) : (
            <table className="kv"><tbody>
              <tr><td>Rule</td><td>within {h.rule.max_distance_m} m, at least {h.rule.min_features} features</td></tr>
              <tr><td>Finding</td><td>{h.finding}</td></tr>
              <tr><td>Source</td><td>{h.source}</td></tr>
            </tbody></table>
          )}
        </section>
      ))}

      <section>
        <h2>The closing step: compose, don&apos;t assert</h2>
        <p>
          Hop 1 says the bridge is inside the flood outline ({d.hops[0].fwd.rcc8}).
          Hop 2 says the outline is inside the maybe-band ({d.hops[1].fwd.rcc8}).
          The composition table for these two relations allows exactly one outcome:
        </p>
        <table className="kv"><tbody>
          <tr><td>Algebra</td><td>{c.step} = [{c.allowed.join(", ")}]</td></tr>
          <tr><td>Observed</td><td>{c.observed} — the frozen study&apos;s own membership for this bridge</td></tr>
          <tr><td>Verdict</td><td>{c.match ? "forced: the observed answer falls inside the allowed set, so the hops entail it" : "MISMATCH — the chain does not support the verdict"}</td></tr>
        </tbody></table>
        <p>{c.meaning}.</p>
        <p className="meta">Hop 3 (reach inside the band) and hop 4 (the damage cluster beside the reach) are the corroborating evidence: the burst story&apos;s witnesses, standing where the relations say they stand.</p>
      </section>

      <section>
        <h2>The time hop</h2>
        <p>{d.temporal.hop}.</p>
        <p className="meta">Honestly skipped: {d.temporal.skipped}.</p>
      </section>

      <section>
        <h2>How to check this by hand</h2>
        <p>Run <span className="meta">python scripts/make_chain.py</span> — it re-reads the frozen pipeline output, recomputes hops 2–3 with the frozen geometry code, looks up hop 4 in the frozen brief, and refuses to write unless the composition matches. Anything the artifacts cannot support is skipped with a printed reason, never filled in.</p>
      </section>
    </main>
  );
}
