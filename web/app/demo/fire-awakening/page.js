export default function FireAwakening() {
  return (
    <main className="demo demo-fire">
      <header className="hero">
        <p className="eyebrow">Showcase · Kalimantan fire, demo six of seven</p>
        <h1>The awakening, and the morning watch</h1>
        <p className="lede">
          For months the archive counted four matching fires and stayed silent. Then the fifth
          closed window arrived — rainforest, brush, and peat in a single shape — and memory
          spoke for the first time. Every morning since, an agent with no model at all pulls
          the sky, checks the past, and writes its lines.
        </p>
        <div className="stats">
          {[
            { n: "5 of 5", l: "matching windows, three continents" },
            { n: "−0.130", l: "shuffled noise scores — cannot invent skill" },
            { n: "+0.270", l: "true signal gains — can hear it" },
          ].map((s) => (
            <div className="stat" key={s.l}>
              <p className="stat-num">{s.n}</p>
              <p className="meta">{s.l}</p>
            </div>
          ))}
        </div>
      </header>

      <section>
        <h2>Four was silence, five was a voice</h2>
        <p className="story-drop">
          A memory that speaks at two matching fires is gossip, so this one is gagged by
          arithmetic until five independent windows share one exact shape — and it proved the
          gag works by scoring below its own frozen baseline on two hundred rounds of shuffled
          noise. Then the backfill landed: one Amazon window, one Texan, one from the western
          United States, two from Kalimantan itself, three continents holding a single hidden
          restart shape. The count crossed, the silence ended, and the second ranking appeared
          beside the frozen one, labelled, capped, and checked against the ledger word by word.
        </p>
      </section>

      <section>
        <h2>The watchman with no mind</h2>
        <p>
          Each morning the agent pulls five days of satellite detections — on October 30th it
          found 675, spiking to eight times the trailing median — scores them with the locked
          September rules, and asks the past whether today&apos;s shape is known. That morning
          it was: four Iberian windows from late September, named with dates and outcomes,
          plus two same-shape windows the agent refused to judge because their scenes had run
          out of future. Four written trigger rules decided a spike study was warranted, and
          the human lines were assembled from templates, every number pre-checked, no model
          writing a single word. The watchman has manners, too: one morning, one brief, with
          reruns cooling down instead of nagging — and if the archive ever moves beneath a
          run, it stays silent rather than briefing from stale numbers. The page had
          named sustained rain as its own falsifier in advance. Then the rain came.
        </p>
        <p><strong>New minds, same verdict.</strong> Two later models were each invited to frame the same fire: both passed the null test in a single round with zero citation errors, each topped a smouldering-restart story of its own naming — and both disagreed with the frozen ledger exactly as the first had, moving the frozen probabilities by 0.0000. Three minds, one untouched arithmetic: eloquence proposes, numbers dispose, which is the division of labour working as designed.</p>
        <p><a href="/demo/fire-study/live">The live page</a> <span className="meta">— run the morning round yourself, in front of everyone.</span></p>
        <p><a href="/demo/fire-study/memory">What the system remembers</a> <span className="meta">— the cases behind the counts.</span></p>
      </section>
    </main>
  );
}
