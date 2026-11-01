export default function NepalTriage() {
  return (
    <main className="demo demo-flood">
      <header className="hero">
        <p className="eyebrow">Showcase · Nepal flood, demo two of six</p>
        <h1>The triage map, and the doctor who said safe</h1>
        <p className="lede">
          While the valley was still blind, two questions burned: where must rescue go first,
          and whom do you trust when the clever machine says all is well? This page answers
          both — a 195-asset rescue ledger, and the day the kernel overruled its own model.
        </p>
        <div className="stats">
          {[
            { n: "171", l: "bridges in the band — ground rescue" },
            { n: "10", l: "power stations — grid survival" },
            { n: "14", l: "helipads — last-resort airlift" },
          ].map((s) => (
            <div className="stat" key={s.l}>
              <p className="stat-num">{s.n}</p>
              <p className="meta">{s.l}</p>
            </div>
          ))}
        </div>
      </header>

      <section>
        <h2>Drawing the country the flood may own</h2>
        <p className="story-drop">
          A flood you cannot see still obeys the shape of the ground. From the last clear
          geometry, forty-eight blind hours, and a conservative bound on how fast a river wave
          travels, the algebra draws two countries on the map: the ground the water was forced
          to touch, and everything within a 172.8 kilometre reach downstream that it could have
          touched unseen. Then every bridge, powerhouse, and landing pad in the valley is sorted
          against those borders and five distance bands, nearest first. No simulation, no
          bathymetry, no twelve-hour supercomputer run — just relations, and an answer in time
          to matter: 171 bridges, 10 power stations, 14 helipads inside the country of maybe.
        </p>
      </section>

      <section>
        <h2>The second doctor disagrees</h2>
        <p>
          The same evidence was shown to the language model, anonymized, three times. The first
          draft topped a story called M_fluvial and failed its null test. The second never
          became a draft at all: the citation audit blocked it with forty-two short-ID errors.
          The third passed clean, topped a story called M6 — &quot;nothing further happens&quot;
          — and still disagreed with the frozen ledger, which had the burst at 0.9426 against
          the safe story&apos;s 0.0009. Had the model been in charge, the valley would have been
          told it was safe. The default-deny gate printed the dissent alongside the numbers and
          let the arithmetic, not the eloquence, decide.
        </p>
        <p className="meta">
          All three rounds sit in the committed setup reports beside the brief, replayable
          offline from eleven committed cassettes with zero network calls.
        </p>
      </section>

      <section>
        <h2>Back to the study</h2>
        <p><a href="/demo/nepal-cascade">The frozen Nepal brief</a> <span className="meta">— the full asset ledger and verdict.</span></p>
        <p><a href="/demo/nepal-cascade/chain">The algebra, hop by hop</a> <span className="meta">— how one bridge&apos;s fate is forced, not asserted.</span></p>
      </section>
    </main>
  );
}
