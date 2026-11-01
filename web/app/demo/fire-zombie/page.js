export default function FireZombie() {
  return (
    <main className="demo demo-fire">
      <header className="hero">
        <p className="eyebrow">Showcase · Kalimantan fire, demo four of seven</p>
        <h1>The zombie fire under the smoke</h1>
        <p className="lede">
          Peat burns underground, vanishes from the satellites for days, and erupts the moment
          crews stand down. This page shows how a disappearance becomes evidence — and how the
          future was kept sealed while it happened.
        </p>
        <div className="stats">
          {[
            { n: "6,142", l: "detections across 30 grid cells" },
            { n: "0.8425", l: "restart story, top of four" },
            { n: "0.0016", l: "the extinguished story, last" },
          ].map((s) => (
            <div className="stat" key={s.l}>
              <p className="stat-num">{s.n}</p>
              <p className="meta">{s.l}</p>
            </div>
          ))}
        </div>
      </header>

      <section>
        <h2>Reading an absence</h2>
        <p className="story-drop">
          For five September days the satellites watched a Borneo peatland burn, go dark across
          a multi-day gap, and burn again in an unbroken run. The lazy reading says the fire
          went out and a new one started. The auditor disagrees, day by day and cell by cell,
          using time itself as an algebra: an interval that ends on Monday and a gap that
          starts on Monday touch — they never merely precede — so a burn, a silence, and a
          burn compose into one continuous smoulder that ducked underground where the sensors
          cannot see. The ledger heard suppression followed by restart at 0.8425, spread at a
          distant 0.1140, burnout at 0.0419, and true extinction last at 0.0016. The fire did
          not die. It held its breath.
        </p>
      </section>

      <section>
        <h2>The future rode along, unread</h2>
        <p>
          The cutoff was derived from the data&apos;s own last day, never chosen by hand, and
          every later detection rode along in the timeline file in a form the prediction path
          cannot read — dates redacted, bytes untouched. When the held-out late-September days
          were finally unsealed after the fingerprint froze, the underground restart was there
          waiting: match, no re-tuning, not one post-cutoff byte ever touched by the verdict.
        </p>
        <p className="meta">Replay it offline, exactly as the runbook does:</p>
        <pre className="receipt"><span className="cmd">python -m agents.autoinsight --inputs demo/fire_study/inputs \
  --rules demo/fire_study/rules.json --domain demo/fire_study/domain.json \
  --out /tmp/fire_replay.json --prompt-log /tmp/fire_prompts \
  --model-round off
diff /tmp/fire_replay.json demo/fire_study/output/brief.json && echo REPLAY-IDENTICAL</span>
{`REPLAY-IDENTICAL`}</pre>
      </section>

      <section>
        <h2>Back to the study</h2>
        <p><a href="/demo/fire-study">The frozen Kalimantan brief</a> <span className="meta">— verdict, evidence, maps, unchanged.</span></p>
      </section>
    </main>
  );
}
