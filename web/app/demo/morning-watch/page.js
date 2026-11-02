export default function MorningWatch() {
  return (
    <main className="demo demo-fire">
      <header className="hero">
        <p className="eyebrow">Showcase · the collaborator, demo seven of seven</p>
        <h1>The watchman who never touches anything</h1>
        <p className="lede">
          Every morning, before any human is awake, a small agent pulls the sky over Borneo,
          studies what fell, consults sixty past fires, decides whether today earns attention,
          and writes two or three human lines. It has no model, no key, no ambitions — and a
          set of manners most software never learns.
        </p>
        <div className="stats">
          {[
            { n: "150", l: "detections on October 30th, ~8× normal" },
            { n: "4 of 5", l: "past cases behind today's shape" },
            { n: "0", l: "model calls, keys, and things touched" },
          ].map((s) => (
            <div className="stat" key={s.l}>
              <p className="stat-num">{s.n}</p>
              <p className="meta">{s.l}</p>
            </div>
          ))}
        </div>
      </header>

      <section>
        <h2>One morning, minute by minute</h2>
        <p className="story-drop">
          The pull comes first: five days of satellite detections over the study box, counted
          by day. Then the frozen September rules read them — the same scoring code, the same
          weights — and the ranking comes back identical to the study, because the sky has not
          changed the arithmetic. Then the past is asked, and on October 30th it answered with
          four Iberian windows at four labelled of the five the bar requires: silent by the
          counts, with the cases shown. Then the decision, by four written rules in fixed
          order: 150 against a trailing median of 18.5 is eight times normal, past the
          two-times bar, so a spike study is earned and the reason is attached. Finally the
          human lines, assembled from templates with every number pre-checked against the
          ledger block — a snippet that fails its check is never published; the run fails
          instead.
        </p>
        <p className="meta">Run the exact morning yourself, offline, with the committed pull:</p>
        <pre className="receipt"><span className="cmd">python -m collab_agent.morning --fixture oct30</span>
{`morning 2026-10-30: trigger=spike (150 detections today against a trailing
median of 18.5 — roughly 8 times the normal level, past the 2x bar)
2026-10-30: 150 detections against a trailing median of 18.5. Frozen rules
read suppression_then_restart at 84.25 support; the stored pattern stands at
4 of 5 labelled. Watch daily counts: near this level the burn run is unbroken.`}</pre>
      </section>

      <section>
        <h2>Manners, not powers</h2>
        <p>
          What makes this agent a collaborator rather than a cron job is restraint, enforced
          by machinery rather than promised in prose. It briefs once per morning: a second
          run the same day reports its cooldown and writes nothing, because a rerun is a nag,
          not news. It hashes the memory store before it reads and re-reads after, and if the
          ground moved beneath it, it stays silent rather than briefing from stale numbers.
          A corrupted notebook starts fresh with a spoken note instead of crashing. And when
          the evolver's proposals earn a human approval, the brief may quote the decision card
          in its steps — quoted, never applied, with the snippet standing byte-identical
          either way. The law is written down: the runner never writes the archive. Digest
          lines and pull copies only.
        </p>
      </section>

      <section>
        <h2>The mind it does not have — yet</h2>
        <p>
          Honesty requires the missing piece named. The agent that mines past failures,
          drafts its own rule changes, and files them for tested replay is specified down to
          the call cap and the read-only tools — but unbuilt. Today a person writes every
          proposal by hand, the machine replays it against held-out fires, and the card
          remembers the verdict. The morning watch goes on regardless, because watching never
          needed a mind. Proposing does, and it is next.
        </p>
        <p><a href="/demo/fire-study/live">The live page</a> <span className="meta">— press the button and the watchman works in front of you.</span></p>
        <p><a href="/demo/fire-study/memory">What the system remembers</a> <span className="meta">— the past the watchman consults.</span></p>
      </section>
    </main>
  );
}
