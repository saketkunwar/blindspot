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
    </main>
  );
}
