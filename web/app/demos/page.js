"use client";

const DEMOS = [
  {
    href: "/demo/nepal-cascade",
    title: "Nepal flood cascade — the frozen verdict",
    body: "Did a valley flood hide a second disaster? The frozen brief named impoundment-then-burst at 0.94 before the ground truth opened — and the quarantined later snapshot confirmed it with 754 newly destroyed features. Includes the validation checks and the full step-by-step procedure.",
  },
  {
    href: "/demo/nepal-cascade/chain",
    title: "Nepal chain — the algebra, hop by hop",
    body: "One bridge, four hops, one forced answer. Follow bridge → flood outline → may-be band → target reach, watch each real relation compose, and see the verdict entailed by compose(NTPP, NTPP) = NTPP rather than asserted.",
  },
  {
    href: "/demo/nepal-cascade/memory",
    title: "Nepal memory — the honestly empty desk",
    body: "Why this study has no memory yet: two dated damage days against 8,368 dateless features. The byte-identity proof that silence changes nothing, and what it would take to fill the desk.",
  },
  {
    href: "/demo/fire-study",
    title: "Kalimantan fire — the frozen verdict, twice tested",
    body: "Suppression, then peat restart at 0.84 — confirmed by a hidden time window and by an identical ranking on half the map. Carries the conditional November outlook and the full step-by-step procedure.",
  },
  {
    href: "/demo/fire-study/live",
    title: "Kalimantan live — today, plus the morning agent",
    body: "The October pull read with the frozen rules, and the centerpiece: press a button and the morning agent runs its round in front of you — pull, study, memory, decision, and its two human lines.",
  },
  {
    href: "/demo/fire-study/memory",
    title: "Fire memory — it speaks: one pattern at 5 of 5",
    body: "Rolling-origin backtests across 14 regions, the null test that keeps memory honest, the as-of slider, the evolution desk — and the new recall tier: the actual past windows behind the counts, nearest first, with what followed. Best pattern at 5 of 5 across three continents — memory speaks.",
  },
  {
    href: "/demo/fire-study/cross-region",
    title: "Cross-region study — does fire rhyme across continents",
    body: "Eleven firegrounds, one frozen key: which patterns repeat across regions and which stay local, the leader at 5 of 5 across three continents, and the three pulls that decided it.",
  },
];

const SHOWCASE = [
  {
    href: "/demo/nepal-blindfold",
    title: "The blindfold reveal",
    body: "The valley's verdict, spoken without ever seeing the aftermath — then the sealed ground truth opened to 754 matching features. With the replay command quoted.",
  },
  {
    href: "/demo/nepal-triage",
    title: "The triage map, and the doctor who said safe",
    body: "195 assets sorted into the country of maybe, and the three rounds where the model cried safe and the kernel overruled it: M_fluvial, 42 citation errors, M6.",
  },
  {
    href: "/demo/nepal-algebra",
    title: "The maths that cannot teleport",
    body: "Directions instead of coordinates, and the gates that bit: the shifted composition table, the vacuous-truth trap, the 313,269-to-one bug that became 1.06.",
  },
  {
    href: "/demo/fire-zombie",
    title: "The zombie fire under the smoke",
    body: "A disappearance read as evidence at 0.8425, with the future riding along sealed and unread until the fingerprint froze. Replay command quoted.",
  },
  {
    href: "/demo/fire-halfmap",
    title: "Cut the map in half",
    body: "Delete the entire eastern half live and watch all four probabilities return to the sixth decimal of zero drift. The exact check, quoted.",
  },
  {
    href: "/demo/fire-awakening",
    title: "The awakening, and the morning watch",
    body: "Four was silence and five was a voice across three continents — then the model-less morning watch, the Iberian lookalikes, and the rain that arrived on cue.",
  },
];

export default function DemosIndex() {
  return (
    <main className="demo demo-index">
      <header className="hero">
        <p className="eyebrow">BlindSpot demos</p>
        <h1>Every demo, one page</h1>
        <p className="lede">
          Each demo below is a frozen, re-runnable claim — not a slideshow. Verdicts replay
          byte-for-byte, holdouts are data rather than prose, and everything silent says why.
        </p>
        <p>
          The thing one pipeline does that few current systems can: reason about what the
          satellites could not see — the days lost to cloud and the ground between clear
          views — in space and time together. That is what every demo on this page exercises.
        </p>
      </header>
      <section>
        <h2>The showcase: six stories, told like stories</h2>
        <p>
          Start here for the presentation. Each story pairs what the engine saw inside the
          sensing gap with the proof it could not have cheated — every command quoted, every
          number carrying its receipt.
        </p>
      </section>
      {SHOWCASE.map((d) => (
        <section key={d.href}>
          <h2><a href={d.href}>{d.title}</a></h2>
          <p>{d.body}</p>
        </section>
      ))}
      {DEMOS.map((d) => (
        <section key={d.href}>
          <h2><a href={d.href}>{d.title}</a></h2>
          <p>{d.body}</p>
        </section>
      ))}
    </main>
  );
}
