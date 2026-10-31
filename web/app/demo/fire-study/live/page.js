"use client";

import { useEffect, useState } from "react";
import { getDemo2Fire } from "../../../../lib/api";

export default function FireLiveDemo() {
  const [brief, setBrief] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDemo2Fire()
      .then((b) => setBrief(b))
      .catch((e) => setError(`API unreachable: ${e.message}`));
  }, []);

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
        <p><a href="/demo/fire-study/memory">What the system remembers</a> <span className="meta">— 48 past episodes, honest silence.</span></p>
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
        <h2>Does the past recognise today?</h2>
        <p>
          {pm.known
            ? `Yes. Today matches the strongest known pattern: ${pm.episodes} past episodes, ${pm.labelled} with known outcomes, all restarts. It stands at ${pm.labelled} of 5 — still silent, one closed window away from speaking.`
            : "No. Today matches no known pattern — an unseen shape of evidence, which the system records rather than forcing into a familiar box."}
        </p>
        <p className="meta">The outcome windows for the last two days are still open, so they cannot be labelled yet — memory never grades unfinished homework.</p>
      </section>

      <section>
        <h2>How we know what we know</h2>
        <p><a href="/demo/fire-study">The frozen September brief</a> <span className="meta">— the verdict, locked and byte-identical.</span></p>
        <p><a href="/demo/fire-study/memory">What the system remembers</a> <span className="meta">— 48 past episodes across 11 regions, and why memory stays silent.</span></p>
      </section>

      <section>
        <h2>Procedure: step by step</h2>
        <p>No language model takes part anywhere below. This page is pure reading: today&apos;s sky through September&apos;s locked rules.</p>
        <p className="lede">Step 1 — Pull today&apos;s sky</p>
        <p>Five days of satellite fire detections for the study box, October 26–30: 675 detections (25, 12, 12, 476, 150 day by day), with the map bounds double-checked and the source matching September&apos;s. The access keys live in the operator&apos;s environment only — never in files or logs. The raw pull lands in a temp folder first, and a copy ships beside this page so every number stays checkable. It never enters the frozen study.</p>
        <p className="lede">Step 2 — Score it with the locked September rules</p>
        <p>The exact same machinery as September — same cell lists, same six facts, same weights — runs over the live slice. The result must equal the frozen ranking to within five hundred-thousandths. It does, identically: no re-tuning, no new weights, no exceptions.</p>
        <p className="lede">Step 3 — Ask the past whether it recognises today</p>
        <p>Today&apos;s evidence shape is looked up against the 48 stored past episodes: it lands inside the best-known pattern — 6 episodes, 4 with known outcomes, all restarts — one case short of the 5 the bar requires. So memory stays silent, and this page says so instead of rounding up.</p>
        <p className="lede">Step 4 — Publish with the boundary on its face</p>
        <p>A snapshot script writes this page&apos;s numbers; the page carries the full timeline (study window, hidden test, live days dated to October 30), states it is a reading and not a forecast, and makes the November outlook conditional both ways — dry return means elevated restart risk, rain holding means the pattern breaks. When the rain arrived after the last pull, no step changed: the next pull verifies it the moment daily counts fall.</p>
      </section>
    </main>
  );
}
