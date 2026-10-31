"use client";

import { useEffect, useState } from "react";
import { getDemo2Fire } from "../../../../lib/api";

export default function FireMemoryDemo() {
  const [brief, setBrief] = useState(null);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(null);

  useEffect(() => {
    getDemo2Fire()
      .then((b) => {
        setBrief(b);
        const days = [...new Set(b.data.episodes.map((e) => e.cutoff))].sort();
        setAsOf(days[days.length - 1]);
      })
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  if (error) return <main className="demo demo-fire"><p className="meta">{error}</p></main>;
  if (!brief || !asOf) return <main className="demo demo-fire"><p className="meta">Loading demo…</p></main>;

  const d = brief.data;
  const ms = d.memory_status;
  const days = [...new Set(d.episodes.map((e) => e.cutoff))].sort();
  const readable = d.episodes.filter(
    (e) => e.label !== "unlabelable" && e.window_end <= asOf);
  const nt = d.null_test;
  const hc = d.hill_climb;
  const edgeMax = Math.max(Math.abs(nt.null_edge), Math.abs(nt.signal_edge));

  return (
    <main className="demo demo-fire">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · the system&apos;s memory <span className="mode">{brief.mode}</span></p>
        <h1>What the system remembers — and what it refuses to claim</h1>
        <p className="lede">
          BlindSpot studies disasters and gives a verdict. For the Kalimantan fires it concluded:
          the fires were suppressed, then the peat restarted. That answer is locked — recomputing it
          always gives the same result, letter for letter. This page shows the system&apos;s memory:
          what it has learned from watching {ms.episodes} replays of past fires, and why it still
          keeps quiet.
        </p>
        <p className="meta">Memory rule {ms.rule_id} · config v4</p>
      </header>

      <section>
        <h2>The locked verdict</h2>
        <p>{d.frozen.verdict}</p>
        <table className="kv"><tbody>
          <tr><td>Top story</td><td>{d.frozen.top_title} — a support score of {(d.frozen.probability * 100).toFixed(1)} out of 100. That is how strongly the evidence backs it, not a prediction of the future.</td></tr>
          <tr><td>Evidence behind it</td><td>{d.frozen.detections.toLocaleString()} satellite detections across {d.frozen.cells} grid cells, weighed into {d.frozen.mechanisms} possible stories.</td></tr>
        </tbody></table>
      </section>

      <section>
        <h2>How the system remembers</h2>
        <p>
          Take the fire records of {ms.scenes} regions. Pick a date. Cover up everything after it,
          and ask the frozen system what it concludes from only what came before. Then uncover the
          next two days and write down what actually happened. Repeat for every date. Each replay
          is called an episode: what the evidence looked like, plus what came true.
        </p>
        <div className="counters">
          {[
            { n: String(ms.episodes), l: "replays (episodes)" },
            { n: String(ms.labelled), l: "with known outcomes" },
            { n: String(ms.scenes), l: "fire regions" },
            { n: String(ms.patterns), l: "distinct patterns" },
          ].map((c) => (
            <div className="counter" key={c.l}>
              <p className="counter-num">{c.n}</p>
              <p className="meta">{c.l}</p>
            </div>
          ))}
        </div>
        <p className="meta">{d.skipped.thin_history} cutoffs were too thin on history and {d.skipped.empty_files} files held no detections — all skipped with the reason printed, never silently dropped.</p>
      </section>

      <section>
        <h2>{ms.speaking ? "It speaks — for the first time" : "Why it stays silent"}</h2>
        <p>
          Memory only speaks when one pattern has <strong>{ms.threshold} past cases</strong> behind
          it. The strongest pattern has <strong>{ms.best_labelled}</strong>.{" "}
          {ms.speaking
            ? "So the bar is met: new briefs gain a second, labelled ranking beside the frozen one — the same adjustment the coin-flip test below already proved cannot invent skill. The five cases are one Amazon, one Texan, one western-US, and two Kalimantan episodes: three continents, one shape."
            : "So every brief leaves the memory section out entirely — and that absence is checked letter-for-letter against the frozen brief, not promised in words."}{" "}
          {d.hook}
        </p>
      </section>

      <section>
        <h2>The one rule that prevents cheating</h2>
        <p>
          Memory may only use what was already known. Move the date back below and watch episodes
          drop out: anything past the line is knowledge the case could not have had yet. The system
          must not grade its own homework. {readable.length} labelled outcomes are readable at {asOf}.
        </p>
        <p className="meta">
          <input type="range" min={0} max={days.length - 1} value={days.indexOf(asOf)}
            onChange={(e) => setAsOf(days[Number(e.target.value)])} aria-label="As-of cutoff" /> {asOf}
        </p>
        <div className="cards">
          {d.episodes.map((e) => {
            const future = e.cutoff > asOf;
            return (
              <div className={"card" + (future ? " quiet" : "")} key={e.episode_id}>
                <p className="meta">{e.episode_id}{future ? " · beyond as-of, unreadable" : ""}</p>
                <p>{e.n_pre.toLocaleString()} detections · {e.cells_pre} cells · next two days: {e.label === "unlabelable" ? "ran out of future to check against" : e.label}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h2>When past fires look alike</h2>
        <p>
          Episodes with the same shape of evidence share a pattern. One pattern below holds slices
          from the Amazon, the western United States, and Kalimantan together — the same kind of
          fire on three continents.
        </p>
        {d.top_patterns.map((p, i) => (
          <div key={i}>
            <p><strong>{p.labeled} known outcomes out of {p.episodes} replays</strong> <span className="meta">({Object.entries(p.labels).map(([k, v]) => `${k}: ${v}`).join(", ")})</span></p>
            <p className="meta">{p.members.join(" · ")}</p>
          </div>
        ))}
      </section>

      <section>
        <h2>Past windows shaped like the study</h2>
        <p>
          The study window itself is a shape the archive has seen before. Below are the nearest
          past windows to it — nearest first, each with its place, its dates, and what followed.
          Counting patterns is the middle tier; this is the bottom one, the actual cases, and the
          two tiers are shown side by side on purpose so you can watch them agree or disagree.
        </p>
        <ol className="steps">
          {(d.recall?.cases || []).map((c) => (
            <li key={c.episode_id}>
              <p><strong>{c.scene}, cutoff {c.cutoff}.</strong></p>
              <p className="meta">
                {c.distance === 0
                  ? "Same evidence shape as the study. "
                  : `Differs in ${c.distance} respect${c.distance === 1 ? "" : "s"} (${c.differing.join(", ")}). `}
                {c.n_pre} detections before the cutoff, {c.n_post} after across {c.window_start} to {c.window_end} — labelled {c.label}, and the frozen story that morning was {c.top_mechanism.replace(/_/g, " ")}.
              </p>
            </li>
          ))}
        </ol>
        {(d.recall?.unlabelled_same_shape || 0) > 0 && (
          <p className="meta">
            {d.recall.unlabelled_same_shape} more window{d.recall.unlabelled_same_shape === 1 ? "" : "s"} with the study&apos;s exact shape exist{d.recall.unlabelled_same_shape === 1 ? "s" : ""} but sit past their scenes&apos; last observed day, so they stay unlabelled rather than guessed. No quiet window has ever been recorded — that absence is part of the memory, stated here instead of buried.
          </p>
        )}
      </section>

      <section>
        <h2>Could the maths invent skill?</h2>
        <p>
          Before trusting the adjustment, it was tested on {nt.trials} rounds of coin flips. With
          random labels it <em>loses</em> points ({nt.null_edge.toFixed(3)}) — chasing noise costs,
          so it cannot manufacture skill. With perfect labels it gains clearly (+{nt.signal_edge.toFixed(3)}),
          so it can recognise the real thing when it arrives. This was a simulation with fixed
          rules ({nt.note.toLowerCase()}), run before any real history existed.
        </p>
        {[
          { label: "Coin-flip labels", edge: nt.null_edge },
          { label: "Perfect labels", edge: nt.signal_edge },
        ].map((b) => (
          <div className="bar-row" key={b.label}>
            <span className="bar-rank">{b.edge >= 0 ? "+" : "−"}</span>
            <span className="bar-label">{b.label}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(Math.abs(b.edge) / edgeMax * 100).toFixed(1)}%` }} />
            </span>
            <span className="bar-num">{b.edge >= 0 ? "+" : ""}{b.edge.toFixed(3)}</span>
          </div>
        ))}
      </section>

      <section>
        <h2>Who gets to change the rules</h2>
        <p>
          The system may suggest a rule change and test it against later episodes — but only a
          person can approve it, with a written reason. Nothing has qualified yet ({hc.candidates_filed} proposals
          filed from {hc.traces_read} logged model calls), so the desk is empty, and the system proves
          it by refusing. One lesson is already written down for later: once memory speaks, a long
          run of uninformative history actively hurts — fixing that is filed as an idea, not
          quietly patched into the maths.
        </p>
      </section>

      <section>
        <h2>Back to the study</h2>
        <p><a href="/demo/fire-study">The frozen Kalimantan fire brief</a> <span className="meta">— verdict, evidence, maps, and conclusions, unchanged.</span></p>
      </section>
    </main>
  );
}
