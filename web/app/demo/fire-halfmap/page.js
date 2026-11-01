export default function FireHalfmap() {
  return (
    <main className="demo demo-fire">
      <header className="hero">
        <p className="eyebrow">Showcase · Kalimantan fire, demo five of six</p>
        <h1>Cut the map in half</h1>
        <p className="lede">
          Delete the entire eastern half of the fire — 3,071 detections gone in one stroke —
          and watch the verdict refuse to flinch. Not by a hundredth. Not by a ten-thousandth.
        </p>
        <div className="stats">
          {[
            { n: "3,071", l: "detections deleted, live" },
            { n: "0.8425", l: "before, and after" },
            { n: "0.000000", l: "largest drift, all four stories" },
          ].map((s) => (
            <div className="stat" key={s.l}>
              <p className="stat-num">{s.n}</p>
              <p className="meta">{s.l}</p>
            </div>
          ))}
        </div>
      </header>

      <section>
        <h2>Why half a map should break everything</h2>
        <p className="story-drop">
          Any verdict built on counting should wobble when half its counts vanish. Slice away
          the east at the median line and 6,126 clumped detections become a remnant — yet the
          machine does not count, it relates. Clumped stays clumped, the gap stays a gap, the
          run stays unbroken, because topology and rhythm survive amputation in a way piles of
          pixels cannot. The same frozen rules over the western remnant return suppression then
          restart at 0.8425, spread at 0.1140, burnout at 0.0419, extinction at 0.0016 — every
          digit identical, the largest drift across all four stories exactly zero.
        </p>
      </section>

      <section>
        <h2>Do it in front of everyone</h2>
        <p>
          The masking is a dozen lines anyone can read: split the detections at their median
          longitude, keep the west, curate into a scratch folder, rescore with the locked rules
          and no model. There is no step where a thumb could touch the scale, because there is
          no step a human performs at all.
        </p>
        <p className="meta">The exact check, byte for byte what the snapshot builder runs:</p>
        <pre className="receipt"><span className="cmd">python -m agents.autoinsight --inputs /tmp/fire_holdout/inputs \
  --rules demo/fire_study/rules.json --domain demo/fire_study/domain.json \
  --out /tmp/fire_holdout/brief.json --model-round off</span>
{`suppression_then_restart  frozen=0.8425  holdout=0.8425  diff=0.000000
continued_spread          frozen=0.1140  holdout=0.1140  diff=0.000000
fuel_burnout              frozen=0.0419  holdout=0.0419  diff=0.000000
sustained_suppression     frozen=0.0016  holdout=0.0016  diff=0.000000
RANKING IDENTICAL TO 4 DECIMALS: True`}</pre>
      </section>

      <section>
        <h2>Back to the study</h2>
        <p><a href="/demo/fire-study">The frozen Kalimantan brief</a> <span className="meta">— the whole map, same answer.</span></p>
      </section>
    </main>
  );
}
