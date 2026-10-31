"use client";

import { useEffect, useState } from "react";
import { getDemo2Fire, runMorning } from "../../../../lib/api";

export default function FireLiveDemo() {
  const [brief, setBrief] = useState(null);
  const [error, setError] = useState("");
  const [run, setRun] = useState(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");

  useEffect(() => {
    getDemo2Fire()
      .then((b) => setBrief(b))
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

  const startRun = () => {
    setRunning(true);
    setRunError("");
    runMorning()
      .then((r) => { setRun(r); setRunning(false); })
      .catch((e) => { setRunError(`The agent could not run: ${e.message}`); setRunning(false); });
  };

  const today = new Date().toISOString().slice(0, 10);

  if (error) return <main className="demo"><p className="meta">{error}</p></main>;
  if (!brief) return <main className="demo"><p className="meta">Loading demo…</p></main>;

  const live = brief.data.live;
  if (!live) return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · live fire watch</p>
        <h1>No live reading available</h1>
        <p className="lede">No live satellite pull has been published yet. The frozen September study and the memory pages below are all current.</p>
      </header>
      <section>
        <h2>Meanwhile</h2>
        <p><a href="/demo/fire-study">The frozen Kalimantan fire brief</a> <span className="meta">— unchanged.</span></p>
        <p><a href="/demo/fire-study/memory">What the system remembers</a> <span className="meta">— 60 past episodes, one pattern speaking.</span></p>
      </section>
    </main>
  );

  const maxDay = Math.max(...live.days.map((x) => x.detections));
  const pm = live.pattern_match;

  return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demo · live fire watch <span className="mode">live data as of {live.as_of}</span></p>
        <h1>Kalimantan is burning right now</h1>
        <p className="lede">
          Fresh satellite detections pulled today show {live.detections} hotspots over the last five
          days in the same study box — including a sharp spike of {live.days.reduce((m, x) => x.detections > m.detections ? x : m, live.days[0]).detections} in
          a single day. This page reads today&apos;s evidence with the frozen September rules. It is a
          reading of now, not a forecast of tomorrow: no forecasting model exists here.
        </p>
        <p className="meta">Source: NOAA-20 VIIRS, same sensor as the September study · every point verified inside the study box · last day still partial</p>
      </header>

      <section>
        <h2>When everything happened</h2>
        <ol className="steps">
          <li><p><strong>September {live.study_window[0].slice(8)}–{live.study_window[1].slice(8)}: the frozen study.</strong></p><p className="meta">Five days of evidence, locked. The verdict pointed at suppression, then peat restart — before seeing anything after.</p></li>
          <li><p><strong>Late September: the hidden test.</strong></p><p className="meta">{live.held_out}. The brief had already named it, unseen.</p></li>
          <li><p><strong>October {live.days[0].day.slice(8)}–{live.as_of.slice(8)}: right now.</strong></p><p className="meta">Fresh satellite detections, read with the same frozen rules. The {live.as_of} count is still growing — the satellites have not finished today yet.</p></li>
        </ol>
      </section>

      <section>
        <h2>The last five days</h2>
        {live.days.map((x) => (
          <div className="bar-row" key={x.day}>
            <span className="bar-rank">{x.day.slice(5)}</span>
            <span className="bar-label">detections{x.day === live.as_of ? " (today, partial)" : ""}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(x.detections / maxDay * 100).toFixed(1)}%` }} />
            </span>
            <span className="bar-num">{x.detections.toLocaleString()}</span>
          </div>
        ))}
        <p className="meta">Late October is burning harder than anything in the September record — but October is a different season, and the rules below were written for September. Read on for what that means.</p>
      </section>

      <section>
        <h2>What today&apos;s evidence says</h2>
        <p className="meta">Today is {today} (your browser&apos;s date). The reading below replays the {live.as_of} satellite pull — treat this page as a demo of the machinery, not a live operations feed: the numbers are real, but they are the {live.as_of} sky, not this morning&apos;s.</p>
        <p>
          Scored with the exact frozen September rules, today&apos;s {live.detections} detections say{" "}
          <strong>{live.ranking[0].title}</strong> at {(live.ranking[0].probability * 100).toFixed(1)} out
          of 100 — {live.matches_frozen ? "the same story as September, identical to all four decimals." : "a different story from September — read the caution below carefully."}
        </p>
        {live.ranking.map((m, i) => (
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
        <h2>Run the morning agent</h2>
        <p>
          This is the centerpiece: the collaborative agent doing its morning round in front of you —
          pulling the sky, studying it with the frozen rules, asking the past, deciding, and writing
          its lines. It runs the October 30 pull as a demo replay (no key, no network, the same code
          path the operator&apos;s cron uses). Press the button and watch each step land below, including
          exactly how — and whether — it used memory.
        </p>
        <p>
          <button type="button" onClick={startRun} disabled={running}>
            {running ? "The agent is working…" : run ? "Run the morning agent again" : "Run the morning agent"}
          </button>
        </p>
        {runError && <p className="meta">{runError}</p>}
        {running && !run && <p className="meta">Pulling, scoring, remembering, deciding…</p>}
        {run && (
          <>
            <p className="meta">Replay of {run.as_of} · trigger: {run.trigger || "quiet"} · frozen ranking {run.matches_frozen ? "reproduced" : "DIFFERS — reported, not adjusted"}</p>
            <ol className="steps">
              {run.steps.map((s, i) => (
                <li key={s.name}>
                  <p><strong>Step {i + 1} — {s.title}.</strong></p>
                  <p>{s.detail}</p>
                  {s.name === "memory" && (
                    <p className="meta">
                      {s.speaks
                        ? `Memory spoke: ${s.labelled} labelled cases clear the bar of ${s.speak_bar}.`
                        : `Memory silent: ${s.labelled} of ${s.speak_bar} labelled cases needed. Nothing rounded up.`}
                    </p>
                  )}
                  {s.name === "decide" && s.trigger && (
                    <p className="meta">The preregistered rule that fired, with its reason — thresholds are versioned, never quietly retuned.</p>
                  )}
                </li>
              ))}
            </ol>
            <p className="lede">The morning lines</p>
            <p><strong>{run.snippet}</strong></p>
            <p className="meta">{run.reason}</p>
          </>
        )}
      </section>

      <section>
        <h2>Does the past recognise today?</h2>
        <p>
          {pm.known
            ? `Yes. Today matches a familiar pattern: ${pm.episodes} past episodes, ${pm.labelled} with known outcomes, all restarts. It stands at ${pm.labelled} of 5 — still silent, one closed window away from speaking.`
            : "No. Today matches no known pattern — an unseen shape of evidence, which the system records rather than forcing into a familiar box."}
        </p>
        <p className="meta">The outcome windows for the last two days are still open, so they cannot be labelled yet — memory never grades unfinished homework.</p>
      </section>

      <section>
        <h2>Windows shaped like today</h2>
        <p>
          Counting is not remembering. Below are the actual past windows the archive holds that look most like today&apos;s — nearest first, each with its place, its dates, and what followed. A near-match names how it differs, so you can see the resemblance instead of taking it on faith.
        </p>
        <ol className="steps">
          {(live.recall?.cases || []).map((c) => (
            <li key={c.episode_id}>
              <p><strong>{c.scene}, cutoff {c.cutoff}.</strong></p>
              <p className="meta">
                {c.distance === 0
                  ? "Same evidence shape as today. "
                  : `Differs in ${c.distance} respect${c.distance === 1 ? "" : "s"} (${c.differing.join(", ")}). `}
                {c.n_pre} detections before the cutoff, {c.n_post} after across {c.window_start} to {c.window_end} — labelled {c.label}, and the frozen story that morning was {c.top_mechanism.replace(/_/g, " ")}.
              </p>
            </li>
          ))}
        </ol>
        {(live.recall?.unlabelled_same_shape || 0) > 0 && (
          <p className="meta">
            {live.recall.unlabelled_same_shape} more window{live.recall.unlabelled_same_shape === 1 ? "" : "s"} with today&apos;s exact shape exist{live.recall.unlabelled_same_shape === 1 ? "s" : ""} but sit past their scenes&apos; last observed day, so they stay unlabelled rather than guessed.
          </p>
        )}
      </section>

      <section>
        <h2>How we know what we know</h2>
        <p><a href="/demo/fire-study">The frozen September brief</a> <span className="meta">— the verdict, locked and byte-identical.</span></p>
        <p><a href="/demo/fire-study/memory">What the system remembers</a> <span className="meta">— 60 past episodes across 11 regions, and the morning one pattern started speaking.</span></p>
      </section>

      <section>
        <h2>Procedure: step by step</h2>
        <p>No language model takes part anywhere below. This page is pure reading: today&apos;s sky through September&apos;s locked rules.</p>
        <p className="lede">Step 1 — Pull today&apos;s sky</p>
        <p>Five days of satellite fire detections for the study box, October 26–30: 675 detections (25, 12, 12, 476, 150 day by day), with the map bounds double-checked and the source matching September&apos;s. The access keys live in the operator&apos;s environment only — never in files or logs. The raw pull lands in a temp folder first, and a copy ships beside this page so every number stays checkable. It never enters the frozen study.</p>
        <p className="lede">Step 2 — Score it with the locked September rules</p>
        <p>The exact same machinery as September — same cell lists, same six facts, same weights — runs over the live slice. The result must equal the frozen ranking to within five hundred-thousandths. It does, identically: no re-tuning, no new weights, no exceptions.</p>
        <p className="lede">Step 3 — Ask the past whether it recognises today</p>
        <p>Today&apos;s evidence shape is looked up against the 60 stored past episodes: it lands inside a familiar pattern — 6 episodes, 4 with known outcomes, all restarts — still one case short of the 5 the bar requires for that shape, so for today&apos;s reading memory stays silent, and this page says so instead of rounding up. (Elsewhere in the archive a different shape has since reached 5 of 5 — see the memory page.)</p>
        <p className="lede">Step 4 — Publish with the boundary on its face</p>
        <p>A snapshot script writes this page&apos;s numbers; the page carries the full timeline (study window, hidden test, live days dated to October 30), states it is a reading and not a forecast, and makes the November outlook conditional both ways — dry return means elevated restart risk, rain holding means the pattern breaks. When the rain arrived after the last pull, no step changed: the next pull verifies it the moment daily counts fall.</p>
      </section>
    </main>
  );
}
