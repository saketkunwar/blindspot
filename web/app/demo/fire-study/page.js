"use client";

import { useEffect, useState } from "react";
import MapPane, { legendOf } from "../../../components/MapPane";
import { getDemoFire, getDemoFireGeo, getDemo2Fire } from "../../../lib/api";

const STEPS = [
  { k: "Detect", d: "FIRMS detections gridded into cells over five pre-cutoff days; hotspot cells tagged at the noise floor." },
  { k: "Classify", d: "Ledger of evidence facts scored against an open mechanism set that includes a cessation story." },
  { k: "Cascade", d: "Scores normalize to support-strength probabilities; the verification gate admits only ledger-grounded claims." },
];

export default function FireStudyDemo() {
  const [brief, setBrief] = useState(null);
  const [geo, setGeo] = useState(null);
  const [mem, setMem] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getDemoFire(), getDemoFireGeo()])
      .then(([b, g]) => { setBrief(b); setGeo(g); })
      .catch((e) => setError(`API unreachable: ${e.message}`));
    getDemo2Fire().then((m) => setMem(m)).catch(() => {});
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
        <p>Most systems interpolate what was seen. BlindSpot reasons about what was not seen — the days lost to cloud and the ground between clear views — in space and time together, and every conclusion carries the relations it came from.</p>
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
        <p>A verdict this strong needs enemies: ground truth the brief never saw, in two independent forms.</p>
        <p className="lede">Time held out</p>
        <p>The ledger only saw detections up to {mem.data.validation.temporal.cutoff_day}. Everything after that — {mem.data.validation.temporal.held_out} — was locked away before the brief was written, and the frozen top story still points straight at it. That is a match the system could not have arranged.</p>
        <p className="lede">Half the map removed</p>
        <p>Same frozen rules, but {mem.data.validation.spatial.masked} ({mem.data.validation.spatial.kept.toLocaleString()} of {mem.data.validation.spatial.total.toLocaleString()} detections kept): the ranking came back identical — same order, same probabilities. The fire signal is everywhere on the map, not one hotspot&apos;s doing.</p>
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
        <h2>Procedure: step by step</h2>
        <p>Everything below can be re-run from the pinned files. Follow the steps and you get every number on this page — no flood code executes anywhere in it.</p>
        <p className="lede">Step 0 — Freeze the world first</p>
        <p>Same discipline as the flood study: the configuration is locked under a version tag, every input file is hash-pinned, undecided settings raise instead of defaulting, and ground truth opens only after the freeze.</p>
        <p className="lede">Step 1 — Grid the fire</p>
        <p>Satellite detections are sorted into tenth-degree map cells holding their day-by-day counts: 6,142 detections over five days (September 16–20) across 30 cells, 28 of them hot. The cutoff, September 20, is read off the data&apos;s last day at curation time — never typed into the prediction. Later September days ride along in a separate timeline file as the sealed envelope.</p>
        <p className="lede">Steps 2 and 3 — Redact, then lock</p>
        <p>A context card inventories the inputs with dates blacked out; a freeze script copies everything into the output folder and records fingerprints. One honest limitation: the fire setup round ran without the card, because card-carrying prompts fail their own audit on real inputs — a recorded issue, not a hidden one.</p>
        <p className="lede">Step 4 — Compute the evidence ledger</p>
        <p>The spec-driven builder evaluates six fire facts over the cell lists: 6,142 detections; 5 distinct burn days; 30 cells with fire; 6,126 detections clumped near hot cells; the longest gap between burn days (the continuity signal, from auditing each cell day-to-day for vanish-and-reappear patterns — the formal shape of suppression-then-restart); and the study-box area as context. Building this study exposed two engine gaps that turned out to be general, so they were fixed in the shared core and proven generic by the flood brief staying byte-identical: cluster counting against a scoped cell list, and a seconds-to-days divisor in time statistics.</p>
        <p className="lede">Step 5 — Do the arithmetic, by hand if you like</p>
        <p>Each story adds the weights of supporting facts and subtracts opposing ones (prior 1 point each; clumping counts double at 2.0; the stay-out story gets a 0.5 caution bonus): restart 5.0, continued spread 3.0, fuel burnout 2.0, sustained suppression −1.25. Converted to shares summing to exactly one (raw they summed to 0.9999, so the same documented rule adds a ten-thousandth to the top entry — the mirror image of the flood correction): 0.8425, 0.1140, 0.0419, 0.0016.</p>
        <p className="lede">Step 6 — Check every machine-written sentence</p>
        <p>The same default-deny gate as the flood study: every number must already exist in the ledger, or the brief is blocked.</p>
        <p className="lede">Step 7 — Hide time, check the answer</p>
        <p>The ledger saw nothing past September 20. The sealed late-September days confirm suppression then restart — the top story matches an outcome it never read.</p>
        <p className="lede">Step 8 — Remove half the map, check the answer again</p>
        <p>The same frozen rules recomputed over the western half only (3,071 of 6,142 detections kept): identical ranking, identical probabilities — possible because scoring depends on which facts are active, not their magnitudes. Every gate still passes on half the map, which is itself the finding: the signal is everywhere, not one hotspot&apos;s doing.</p>
        <p className="lede">Step 9 — The model&apos;s round</p>
        <p>The same model, shown only the anonymized pre-cutoff ledger, drafted six mechanisms with its own weights — highest on the unbroken run (0.95) and hotspot clumping (0.9), the same two lead facts the frozen brief leans on — topped smoldering-restart, passed the null test, and disagreed with the frozen top. Expected: framing without conviction. The key was needed once; re-runs replay the recording offline.</p>
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

      <section>
        <h2>Looking ahead: the first week of November</h2>
        <p className="lede">This is an outlook, not a forecast</p>
        <p>Nothing in this pipeline predicts the weather. There is no rain model, no wind model, and no forecast anywhere in the system — what follows is the validated September finding pointed at today&apos;s live data, extended one week forward. Read it as a watch brief, not a prediction.</p>
        <p className="lede">Where things stand on October 30</p>
        <p>The five live days (October 26–30) brought 675 satellite detections, with 476 of them on October 29 alone — the heaviest single day in the window. That shape matches the stored restart pattern in four of five past cases: long burning, peat character, the same signature as the September episode that ended in restart. Since then, news reports say rain has eased the fire — that rain falls after our last satellite pull, so it is not yet confirmed in our data, and the next live pull will verify it the moment daily counts fall.</p>
        <p className="lede">What that means for November 1–7, if things remain as they are</p>
        <p>The outlook below is conditional on the dry regime returning. If the rain holds through the week and the ground stays wet, the pattern breaks: restart risk for the first week of November drops, and the live reading should move out of the restart signature on the next pull. But if dry weather returns and things go back to how they were — counts climbing back toward the October 29 spike of 476 — then the opening days of November carry an elevated restart risk in the same peat blocks. The honest extension of the validated finding is that this pattern restarts rather than dies out whenever it stays dry. The single biggest thing to watch is the daily count: counts staying near spike level mean the burn run is unbroken; a new multi-day gap would reset the clock, exactly as the September gap did before the restart.</p>
        <p className="lede">What would prove this wrong</p>
        <p>A wet week is precisely what breaks the pattern — and per news reports, that week may have started. Sustained rain moves the live reading out of the restart signature, and the next pull will show it. The satellites see heat, not causes, so suppression on the ground can also end the episode in ways no detection count will announce in advance. And one caution from the ledger itself: the archive holds 26 restarts and zero quiets, so the system has never yet watched a matched pattern go quiet — a rain-quenched quiet would be new evidence, recorded as a fifth labelled case, and it is the case that finally lets memory speak.</p>
      </section>
    </main>
  );
}
