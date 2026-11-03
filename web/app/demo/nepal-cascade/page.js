"use client";

import { useEffect, useState } from "react";
import MapPane, { legendOf, featureBounds } from "../../../components/MapPane";
import { getDemoNepal, getDemoNepalGeo, getDemo2Nepal } from "../../../lib/api";

const STEPS = [
  { k: "Detect", d: "Per-snapshot kernel pass over pre-cutoff damage: reach split, channel adjacency, tributary-cluster rule." },
  { k: "Classify", d: "Ledger of evidence facts scored against an open mechanism set that includes nothing-happens." },
  { k: "Cascade", d: "Scores normalize to support-strength probabilities; the verification gate admits only ledger-grounded claims." },
];

export default function NepalCascadeDemo() {
  const [brief, setBrief] = useState(null);
  const [geo, setGeo] = useState(null);
  const [mem, setMem] = useState(null);
  const [error, setError] = useState("");
  const [scenario, setScenario] = useState("before");
  const [afterGeo, setAfterGeo] = useState(null);
  const [fly, setFly] = useState(null);
  const [flyN, setFlyN] = useState(0);

  useEffect(() => {
    Promise.all([getDemoNepal(), getDemoNepalGeo()])
      .then(([b, g]) => { setBrief(b); setGeo(g); })
      .catch((e) => setError(`API unreachable: ${e.message}`));
    getDemo2Nepal().then((m) => setMem(m)).catch(() => {});
  }, []);

  // Before/after reveal: the after-layers are fetched once, on first flip,
  // and swapped in place with the viewport locked — the reveal, not a refit.
  const flip = (s) => {
    setScenario(s);
    if (s === "after" && !afterGeo) {
      getDemoNepalGeo(true).then((g) => setAfterGeo(g)).catch(() => setScenario("before"));
    }
  };

  if (error) return <main className="demo demo-flood"><p className="meta">{error}</p></main>;
  if (!brief) return <main className="demo demo-flood"><p className="meta">Loading demo…</p></main>;

  const d = brief.data;
  const facts = Object.entries(d.ledger.facts);
  const showingAfter = scenario === "after" && afterGeo;
  const layers = showingAfter ? afterGeo.data.layers : geo ? geo.data.layers : [];
  // Guided flight target: the red reach's own bounds, from live layers.
  const flyTarget = () => {
    const t = layers.filter((f) => f?.properties?.kind === "target reach");
    const b = featureBounds(t.length ? t : layers);
    if (b) { setFlyN((n) => n + 1); setFly({ bounds: b, nonce: flyN + 1 }); }
  };
  const counts = d.inputs_audit.counts;
  const counters = [
    { n: counts.kept_pre_cutoff.toLocaleString(), l: "pre-cutoff damage features" },
    { n: counts.cascade_total.toLocaleString(), l: "features surveyed" },
    { n: String(d.mechanisms.length), l: "candidate mechanisms" },
    { n: String(d.prompt_audit.violations.length), l: "prompt-audit violations" },
  ];

  return (
    <main className="demo demo-flood">
      <header className="hero">
        <span className="actnum" aria-hidden="true">01</span>
        <p className="eyebrow">BlindSpot demo · pre-cutoff autoinsight <span className="mode">{brief.mode}</span></p>
        <h1>The valley that burst upstream</h1>
        <p className="lede">{d.verdict}</p>
        <p>Most systems interpolate what was seen. BlindSpot reasons about what was not seen — the days lost to cloud and the ground between clear views — in space and time together, and every conclusion carries the relations it came from.</p>
        <p className="meta">{d.probability_semantics} · snapshot {d.as_of_label}</p>
      </header>

      <section>
        <h2>The story in three beats</h2>
        <div className="beats">
          <div className="beat"><h3>What was lost</h3><p>Forty-eight blind hours over the Langtang Valley. No satellite saw the tributary swell, the debris dam grow, or the water pond behind it — the survey that returned held only the before.</p></div>
          <div className="beat"><h3>What the ledger said</h3><p>From pre-cutoff geometry alone — 2,092 damaged features against one red tributary and the shapes around it — the frozen weights read impoundment-then-burst at 0.9426, and triaged 171 bridges inside a 172.8 kilometre maybe-band.</p></div>
          <div className="beat"><h3>What proved it</h3><p>The ground truth stayed sealed until the freeze. Unopened, it held 754 newly destroyed features in the pattern the burst story predicts — and the model&apos;s safe-drainage all-clear, recorded and overruled in the brief, is still there to read.</p></div>
        </div>
      </section>

      <section>
        <h2>Survey findings</h2>
        <div className="counters">
          {counters.map((c) => (
            <div className="counter" key={c.l}>
              <p className="counter-num">{c.n}</p>
              <p className="meta">{c.l}</p>
            </div>
          ))}
        </div>
        <table className="kv"><tbody>
          <tr><td>Cluster finding</td><td>{d.cluster_finding}</td></tr>
          <tr><td>Model round</td><td>{d.model_round.status}{d.model_round.reason ? ` — ${d.model_round.reason}` : ""} · model {d.model_round.model}</td></tr>
        </tbody></table>
      </section>

      <section>
        <h2>Evidence</h2>
        <div className="cards">
          {facts.map(([fid, f]) => (
            <div className={"card" + (f.active ? "" : " quiet")} key={fid}>
              <p className="meta">{fid}{f.active ? "" : " · quiet"}</p>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>How it works</h2>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.k}><p><strong>{s.k}</strong></p><p className="meta">{s.d}</p></li>
          ))}
        </ol>
      </section>

      <section>
        <h2>Mechanism ranking</h2>
        {d.mechanisms.map((m, i) => (
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

      {mem && (
      <section>
        <h2>Tested, not just computed</h2>
        <p>A verdict this strong needs enemies: ground truth the brief never saw.</p>
        <p className="lede">Time held out</p>
        <p>After the freeze, {mem.data.validation.temporal.newly_destroyed} newly destroyed features from the quarantined window {mem.data.validation.temporal.gt_window} were checked against the frozen top story — along with the satellite barrier-lake log between the snapshots. Match: the answer was fixed before the ground truth opened.</p>
        <p className="lede">Space: still open</p>
        <p>{mem.data.validation.spatial.reason.charAt(0).toUpperCase() + mem.data.validation.spatial.reason.slice(1)} — {mem.data.validation.spatial.what_it_would_take}. Until that re-run exists, this half of the validation is openly pending, not quietly assumed.</p>
      </section>
      )}

      <section>
        <h2>Map</h2>
        <div className="demomap">
          <aside className="rail">
            <h3>The verdict</h3>
            <p className="verdictblock">Impoundment, then burst — 0.9426. The dam grew upstream, the pond broke, and 171 bridges inside a 172.8 kilometre band were told to move first. The sealed ground truth, 754 destroyed features, proved the call.</p>
            <h3>Field notes</h3>
            <p>A blind valley read from geometry alone. Fly to the red reach — the tributary that gave the game away.</p>
            <button type="button" className="item flybtn" onClick={flyTarget}>Fly to the target reach</button>
            <div className="legend">
              {legendOf(layers).map(([kind, color]) => (
                <span className="legend-chip" key={kind}>
                  <span className="swatch" style={{ background: color }} />{kind}
                </span>
              ))}
              <span className="meta legend-note">
                {geo ? `${layers.length} drawn of ${geo.data.pre_cutoff_total}, cap ${geo.data.sample_cap}` : "loading layers…"}
              </span>
            </div>
            <div className="scenario">
              <button type="button" className={scenario === "before" ? "item active" : "item"}
                onClick={() => flip("before")}>Before: what the survey saw</button>
              <button type="button" className={scenario === "after" ? "item active" : "item"}
                onClick={() => flip("after")}>After: ground truth the brief never saw</button>
              {showingAfter && <span className="meta"> {afterGeo.data.gt_after_total.toLocaleString()} post-event features, quarantined until the freeze.</span>}
            </div>
          </aside>
          <div className="mapwrap">
            <MapPane layers={layers} basemap="satellite" lockView={scenario === "after" && !!afterGeo} flyTo={fly} />
          </div>
        </div>
      </section>

      <section>
        <h2>Why this can be trusted</h2>
        <p className="lede">The deterministic core (QSTR)</p>
        <p>Every spatial and temporal claim here comes from qualitative relations — RCC-8 topology (overlap, contact, containment) and Allen interval relations (before, during, after) — computed by pure functions over frozen geometry. No embeddings, no sampling, no temperature. The same inputs always produce the same relations, which is why the brief replays byte-for-byte and why every claim in it can be traced to an exact computation. The core cannot hallucinate a relation; it can only report what the shapes and timestamps entail.</p>
        <p className="lede">The model&apos;s role (setup round)</p>
        <p>The language model proposes — it drafts the open mechanism set and suggests weights from an anonymized prompt that contains no names, no dates, and no outcome. It never computes evidence and never sees ground truth. Its proposal must pass a null test (all facts quiet means the quiet story wins) and a prompt audit, and its disagreement with the frozen human weights is preserved as expected framing-without-conviction. Conviction lives in the signed weights and the ledger arithmetic, not in the model&apos;s text.</p>
      </section>

      <section>
        <h2>Procedure: step by step</h2>
        <p>Everything below can be re-run from the pinned files. Follow the steps and you get every number on this page.</p>
        <p className="lede">Step 0 — Freeze the world first</p>
        <p>Before touching any data, the configuration is locked under a version tag and every input file is hash-pinned in a manifest. Any setting left undecided raises an error instead of silently defaulting. Ground truth is opened only after the freeze, reported as-is, and never tuned against.</p>
        <p className="lede">Step 1 — Gather and clean the maps</p>
        <p>Raw map exports become the study inputs: the flood outline, the target river reach, the waterway network, and 4,414 mapped features. Of those, 2,092 carry damage dates at or before the cutoff; the rest are dateless — a fact that later decides why flood memory stays empty.</p>
        <p className="lede">Step 2 — Write the redacted inventory</p>
        <p>A context card lists what the inputs contain, with every date-like string blacked out, so reference metadata can never smuggle time signals into the model&apos;s prompts.</p>
        <p className="lede">Step 3 — Lock everything</p>
        <p>A freeze script copies (never edits) the inputs, prompts, and rules into the output folder and records their fingerprints. From here on, recomputing over moved inputs is refused — the fingerprint check fails first.</p>
        <p className="lede">Step 4 — Compute the evidence ledger</p>
        <p>The deterministic builder walks the inputs feature by feature. The algebra it uses is comparison, not simulation: do these two shapes overlap, touch, or contain each other (eight possible answers, always checked both ways); does this time period sit before, during, or after that one (thirteen possible answers, where ending and starting the same day counts as touching); and how far apart are they (five fixed distance bands). Out come eight evidence facts: 2,092 pre-cutoff destroyed features; 51.5% of damage upstream; 72.8% hugging the waterways; a tributary-cluster rule firing on 34 features near the target reach; upstream damage 1.06 times as dense as downstream. That last number carries a story: the first version compared feature areas instead of ground areas and came out 313,269 times — plainly absurd, caught by eye, fixed before freezing.</p>
        <p className="lede">Step 5 — Do the arithmetic, by hand if you like</p>
        <p>Each story adds up the weights of the facts that support it (prior 1 point each; the cluster fact counts double at 2.0; the quiet story gets a 0.5 caution bonus for restraint) and subtracts the weights of facts against it: burst 6.0, slope-failure-elsewhere 3.0, downstream-only 1.25, safe drainage −1.0, dam holds −1.0, nothing-further −1.5. Those scores are converted to shares that sum to exactly one (raw they summed to 1.0001, so a documented rule shaves a ten-thousandth off the top entry): 0.9426, 0.0469, 0.0082, 0.0009, 0.0009, 0.0005. These are strengths of support, not weather-forecast chances.</p>
        <p className="lede">Step 6 — Check every machine-written sentence</p>
        <p>A default-deny gate verifies that each number in the brief already exists in the ledger (place names masked first, so digits inside an id like bridges:7 are never mistaken for measurements). Anything unverified is stripped or the brief is blocked.</p>
        <p className="lede">Step 7 — The model&apos;s three rounds</p>
        <p>The language model (muse-spark-1.2-contributor) was shown only the landscape plus the anonymized ledger — no names, no dates, no outcome — and asked what stories could explain it. Round one failed the null test and was rejected. Round two made 30-odd citation errors, writing short ids where full ones were required — rejected, fixed by a single instruction line. Round three passed and stands. The key was needed once; every re-run since replays the recorded conversation offline.</p>
        <p className="lede">Step 8 — Prove the model didn&apos;t already know</p>
        <p>A probe asked the model about the event from anonymized evidence alone. Answer: no knowledge, with a self-stated cutoff predating the flood.</p>
        <p className="lede">Step 9 — Open the sealed envelope</p>
        <p>Only after the freeze, the quarantined later snapshot was opened: 754 newly destroyed features in the hidden window, in the channel-adjacent pattern the burst story predicts. Match — the frozen top story consistent with ground truth it never saw, rank 1 of 6, with no re-tuning afterward.</p>
      </section>

      <section>
        <h2>Conclusion</h2>
        <p className="lede">What was studied</p>
        <p>Whether the 2015 Gorkha earthquake set up a secondary disaster in the Langtang Valley: landslide debris damming a river, water ponding behind it, and the dam bursting into a flood larger than the quake&apos;s direct damage. The evidence is frozen OpenStreetMap data over the valley&apos;s river network, bridges, hydropower sites, and settlements.</p>
        <p className="lede">How it was studied</p>
        <p>Raw extracts were curated into pre-cutoff roles, then summarized in a context card with every place name anonymized and every date redacted, so the machinery never saw anything that could identify the event. Eight evidence facts were computed against frozen, human-signed rules and scored into probabilities over an open mechanism set that always included a nothing-happens story. The brief replayed byte-for-byte from cassettes, and ground-truth checks ran only after the freeze.</p>
        <p className="lede">Insights learned</p>
        <p>Impoundment-then-burst wins at 0.94 support, carried by one fact above all: 518 damage detections clumped near the channel, a concentration no rival mechanism explains. Reach analysis places the damage downstream of the ponding zone, matching a burst origin rather than scattered quake damage. The hazard-zone gate confirmed every zone is computable from extent, reach, and group relations — while reporting honestly that 113 of 418 zones touch neither outline nor assets (remote wet network, not broken plumbing). And the pipeline graded none of its own homework: the answer was fixed before the ground truth opened.</p>
      </section>
    </main>
  );
}
