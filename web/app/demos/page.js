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
    title: "Fire memory — 48 past cases, one short of speaking",
    body: "Rolling-origin backtests across 11 regions, the null test that keeps memory honest, the as-of slider, and the empty evolution desk. Best pattern stands at 4 labelled of the 5 the bar requires.",
  },
];

export default function DemosIndex() {
  return (
    <main className="demo">
      <header className="hero">
        <p className="eyebrow">BlindSpot demos</p>
        <h1>Every demo, one page</h1>
        <p className="lede">
          Each demo below is a frozen, re-runnable claim — not a slideshow. Verdicts replay
          byte-for-byte, holdouts are data rather than prose, and everything silent says why.
        </p>
      </header>
      {DEMOS.map((d) => (
        <section key={d.href}>
          <h2><a href={d.href}>{d.title}</a></h2>
          <p>{d.body}</p>
        </section>
      ))}
    </main>
  );
}
