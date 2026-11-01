export default function NepalBlindfold() {
  return (
    <main className="demo demo-flood">
      <header className="hero">
        <p className="eyebrow">Showcase · Nepal flood, demo one of seven</p>
        <h1>The blindfold reveal</h1>
        <p className="lede">
          Anyone can predict a disaster after seeing the aftermath. This page proves, live and
          without network, that the valley&apos;s verdict was spoken blindfolded — and that the
          sealed ground truth matched it feature for feature.
        </p>
        <div className="stats">
          {[
            { n: "0.9426", l: "burst story, spoken blind" },
            { n: "754", l: "hidden features that confirmed it" },
            { n: "rank 1", l: "truth against the frozen ranking" },
          ].map((s) => (
            <div className="stat" key={s.l}>
              <p className="stat-num">{s.n}</p>
              <p className="meta">{s.l}</p>
            </div>
          ))}
        </div>
      </header>

      <section>
        <h2>What hid between the satellite passes</h2>
        <p className="story-drop">
          Heavy mountain rain fell on the Langtang Valley, and then the clouds closed like a
          curtain. When they opened again, the valley floor had changed. The easy reading was
          runoff: water comes down, damage spreads out. But 2,092 dated scars from before the
          blackout told a stranger story. Over half the damage crowded upstream, nearly
          three-quarters of it hugged the channels, the upstream ground was packed 1.06 times
          denser with destruction than below, and 34 ruined features clustered tight around one
          tributary reach like mourners around a door. That is not the signature of water
          running away. It is the signature of water stopped, held, and then released all at
          once: a landslide dam that filled in the dark and burst.
        </p>
        <p>
          The frozen weights combined those facts into a verdict of <strong>impoundment then
          burst at 0.9426</strong>, with the nearest rival, a slope failure elsewhere, marooned
          at 0.0469. A bold call to make about days no satellite ever saw.
        </p>
      </section>

      <section>
        <h2>Why the blindfold is real, not promised</h2>
        <p>
          The quarantine is built into the machinery, not the honor system. The rival stories
          are drafted from pre-breakup data by a step that structurally cannot receive later
          values, the prediction path is re-run with every raw input hidden to prove it reads
          zero post-cutoff bytes, and the ground-truth window sat sealed behind a recorded
          fingerprint until the verdict was locked. Only then was it opened.
        </p>
        <p className="meta">Run the replay yourself, offline, in seconds:</p>
        <pre className="receipt"><span className="cmd">python3 -m agents.autoinsight --model-round on --out /tmp/replay.json --prompt-log /tmp/replay_prompts
diff /tmp/replay.json demo/nepal_cascade/output/brief.json && echo REPLAY-IDENTICAL</span>
{`REPLAY-IDENTICAL
python3 demo/nepal_cascade/gt_check.py   # unseals the quarantined window: 754 newly
                                         # destroyed features, MATCH, rank 1, zero re-tuning`}</pre>
      </section>

      <section>
        <h2>The moment the seal broke</h2>
        <p>
          Seven hundred and fifty-four features the system had never been allowed to see lit up
          in exactly the channel-adjacent pattern the blind verdict had named. Not near it.
          Exactly it. That is the whole trick of this page: a machine that said what would be
          found, before it was permitted to look, and was right.
        </p>
        <p><a href="/demo/nepal-cascade">The frozen Nepal brief</a> <span className="meta">— verdict, evidence, maps, unchanged.</span></p>
      </section>
    </main>
  );
}
