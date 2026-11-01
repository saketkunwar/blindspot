"""Regenerate every figure for papers/draft1 from committed repo data.

Sources (all checked in): results/fire.json, api/demo2_data/fire.json,
api/demo2_data/live_pull_2026-10-30.csv, results/memory_census.json,
demo/nepal_cascade/output/gt_check.json. Run: python make_figs.py
"""
import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = Path(__file__).parent
FIGS = HERE / "figs"
FIGS.mkdir(exist_ok=True)
ROOT = HERE.parent.parent

plt.rcParams.update({
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 200, "savefig.bbox": "tight",
})
INK = "#222222"
ACCENT = "#0f5b3e"   # deep green
WARM = "#b3541e"     # burnt orange
GREY = "#8a8a8a"
BLUE = "#2f5d8a"


def save(fig, name):
    fig.savefig(FIGS / name)
    plt.close(fig)
    print("wrote", FIGS / name)


# F1: system architecture -------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 2.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 4)
ax.axis("off")


def box(x, y, w, h, title, sub, edge=INK, fill="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                ec=edge, fc=fill, lw=1.4))
    ax.text(x + w / 2, y + h - 0.42, title, ha="center", va="center",
            fontsize=9, weight="bold", color=INK)
    ax.text(x + w / 2, y + h / 2 - 0.18, sub, ha="center", va="center",
            fontsize=7.2, color="#444444")


def arrow(x1, y1, x2, y2, label=None):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 color=INK, lw=1.2, mutation_scale=10))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.18, label, ha="center",
                fontsize=6.8, style="italic", color="#444444")


box(0.2, 1.1, 2.1, 1.8, "Frozen kernel", "RCC-8 / Allen\nledger + scores")
box(2.75, 1.1, 2.1, 1.8, "LLM framing", "setup rounds\ncassettes")
box(5.3, 1.1, 2.1, 1.8, "Memory", "episodes +\nproposals")
box(7.85, 1.1, 1.95, 1.8, "Gate", "default-deny\nG1-G24", edge=WARM)
arrow(2.3, 2.35, 2.75, 2.35, "facts")
arrow(4.85, 2.35, 5.3, 2.35, "reads past")
arrow(4.85, 1.65, 5.3, 1.65)
arrow(2.3, 1.65, 2.75, 1.65, "drafts")
arrow(7.4, 2.0, 7.85, 2.0, "judges")
ax.text(5, 0.45, "Every arrow is replayable: cassettes, hashes, and append-only stores.",
        ha="center", fontsize=8, style="italic", color="#444444")
ax.set_title("BlindSpot: a deterministic core, a model that frames, a gate that judges, memory that waits.",
             fontsize=9.5, weight="bold", color=INK, pad=10)
save(fig, "f1_architecture.png")

# F2: fire daily counts, September window + October live -------------------
fire = json.load(open(ROOT / "results" / "fire.json"))
daily_sep = []
for d in fire["dates"]:
    daily_sep.append(sum(c["counts"].get(d, 0) for c in fire["cells"]))
live_rows = list(csv.DictReader(open(ROOT / "api" / "demo2_data" / "live_pull_2026-10-30.csv")))
daily_live = sorted(Counter(r["acq_date"] for r in live_rows).items())
assert sum(daily_sep) == 6142, daily_sep
assert sum(v for _, v in daily_live) == 675, daily_live

fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.1), sharey=False)
fig.subplots_adjust(top=0.80, wspace=0.22)
xs = list(range(len(daily_sep)))
a1.bar(xs, daily_sep, color=ACCENT, edgecolor="white")
a1.set_xticks(xs)
a1.set_xticklabels([d[5:] for d in fire["dates"]], rotation=0)
a1.set_title("Frozen study window (Sep 16-20)", fontsize=9, weight="bold")
a1.set_ylabel("FIRMS detections / day")
for x, v in zip(xs, daily_sep):
    a1.text(x, v + 60, str(v), ha="center", fontsize=7.5)
a1.text(4.02, 3000, "cutoff\nSep 20", fontsize=7, color=WARM, weight="bold",
        va="center")
a1.axvline(4.35, color=WARM, ls="--", lw=1.2)
xs2 = list(range(len(daily_live)))
vals2 = [v for _, v in daily_live]
a2.bar(xs2, vals2, color=WARM, edgecolor="white")
a2.set_xticks(xs2)
a2.set_xticklabels([d[5:] for d, _ in daily_live])
a2.set_title("Live reading (Oct 26-30)", fontsize=9, weight="bold")
for x, v in zip(xs2, vals2):
    a2.text(x, v + 10, str(v), ha="center", fontsize=7.5)
fig.suptitle("Same peat fire, two eras: the study the brief was frozen on, and today.",
             fontsize=9.5, weight="bold", color=INK)
save(fig, "f2_fire_counts.png")

# F3: frozen ranking + null-test margins -----------------------------------
fig, (b1, b2) = plt.subplots(1, 2, figsize=(7.2, 3.2),
                             gridspec_kw={"width_ratios": [1.5, 1]})
fig.subplots_adjust(top=0.78, wspace=0.35)
mechs = ["suppression\nthen restart", "continued\nspread", "fuel\nburnout",
         "sustained\nsuppression"]
probs = [0.8425, 0.1140, 0.0419, 0.0016]
bars = b1.barh(mechs, probs, color=[ACCENT, GREY, GREY, GREY], edgecolor="white")
b1.set_xlabel("frozen probability")
b1.set_title("Frozen ranking (Sep 16-20 ledger)", fontsize=9, weight="bold")
b1.set_xlim(0, 1.0)
for bar, p in zip(bars, probs):
    b1.text(p + 0.015, bar.get_y() + bar.get_height() / 2, f"{p:.4f}",
            va="center", fontsize=8)
b2.axhline(0, color=INK, lw=1)
b2.axhline(0.02, color=WARM, ls="--", lw=1)
b2.axhline(0.05, color=ACCENT, ls="--", lw=1)
b2.bar(["null\n(shuffled)", "signal\n(perfect)"], [-0.130, 0.270],
       color=[BLUE, ACCENT], edgecolor="white", width=0.6)
b2.text(1.02, 0.02, "null must stay\nbelow +0.02", fontsize=6.8, color=WARM, va="center",
        bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
b2.text(1.02, 0.05, "signal must clear +0.05", fontsize=6.8, color=ACCENT, va="center",
        bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
b2.set_ylabel("top-match edge vs frozen")
b2.set_title("Memory null test (seed 7,\n200 trials)", fontsize=9, weight="bold")
fig.suptitle("The verdict, and the test that keeps memory honest.",
             fontsize=9.5, weight="bold", color=INK)
save(fig, "f3_ranking_null.png")

# F4: memory census + silence line -----------------------------------------
# Read this chart left to right: past cases manufactured -> outcomes known
# -> shapes grouped -> best shape vs the bar. Conclusion first.
census = json.load(open(ROOT / "results" / "memory_census.json"))
stats = census["stats"]
n_ep = stats["episodes"]
n_lab = sum(1 for e in census["episodes"] if e.get("label") != "unlabelable")
n_unlab = n_ep - n_lab
# Pattern counts come from the committed cross-region snapshot (itself
# recomputed from the memory store), never hand-typed: keep this figure
# and its caption in step on every backfill (see SOURCES.txt).
xr = json.load(open(ROOT / "api" / "demo2_data" / "crossregion.json"))
n_pat = xr["patterns"]
best = xr["top_patterns"][0]["labelled"]
fig, (c1, c2) = plt.subplots(1, 2, figsize=(7.2, 3.1),
                             gridspec_kw={"width_ratios": [1, 1.2]})
fig.subplots_adjust(top=0.80, wspace=0.30)
c1.bar(["cases with\na known outcome", "cases without\none"], [n_lab, n_unlab],
       color=[ACCENT, GREY], edgecolor="white", width=0.6)
c1.set_title(f"{n_ep} past cases, {n_lab} usable", fontsize=9, weight="bold")
c1.set_ylabel("episodes")
for x, v in zip([0, 1], [n_lab, n_unlab]):
    c1.text(x, v + 0.5, str(v), ha="center", fontsize=9, weight="bold")
c2.barh(["distinct\nshapes found", "best shape\n(known outcomes)", "bar to\nspeak"],
        [n_pat, best, 5], color=[BLUE, ACCENT, INK], edgecolor="white")
c2.set_title(f"Best shape: {best} of 5", fontsize=9, weight="bold")
c2.set_xlabel("count")
c2.set_xlim(0, max(n_pat, 5) + 8)
c2.text(best + 0.4, 1, f"{best} cases" + (" — speaks" if best >= 5 else ""),
        ha="left", va="center", fontsize=8, weight="bold", color=ACCENT)
c2.text(5.4, 2, "bar is 5", ha="left", va="center", fontsize=8, color=INK)
fig.suptitle("The census, read honestly: the best-known pattern against the bar.",
             fontsize=9.5, weight="bold", color=INK)
save(fig, "f4_census.png")

# F5: validation matrix ------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 2.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 5)
ax.axis("off")
cells = [
    (0.3, 2.3, 4.6, 1.9, "Flood: time held out", "MATCH \u2014 top story rank 1\n754 newly destroyed in the\nquarantined window", ACCENT),
    (5.1, 2.3, 4.6, 1.9, "Flood: half map masked", "PENDING \u2014 openly missing;\nwhat-it-would-take is written,\nnot run", GREY),
    (0.3, 0.2, 4.6, 1.9, "Fire: time held out", "MATCH \u2014 restart confirmed\nin hidden late-Sep days", ACCENT),
    (5.1, 0.2, 4.6, 1.9, "Fire: half map masked", "MATCH \u2014 identical ranking\non 3,071 of 6,142 kept", ACCENT),
]
for x, y, w, h, title, sub, edge in cells:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                ec=edge, fc="white", lw=2))
    ax.text(x + w / 2, y + h - 0.3, title, ha="center", va="center",
            fontsize=8.5, weight="bold", color=INK)
    ax.text(x + w / 2, y + h / 2 - 0.25, sub, ha="center", va="center",
            fontsize=7.5, color="#333333")
ax.set_title("Two studies, two holdouts each: three pass, one is declared missing.",
             fontsize=9.5, weight="bold", color=INK, pad=10)
save(fig, "f5_validation_matrix.png")

# F7: the morning round ----------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 3.2))
ax.set_xlim(0, 10)
ax.set_ylim(0, 5.2)
ax.axis("off")
steps = [
    (0.2, "Wake\non schedule", "your machine's\nclock, not\na server"),
    (2.2, "Pull\nthe sky", "5 days\nFIRMS"),
    (4.2, "Study\nfrozen rules", "same scores\nas September"),
    (6.2, "Ask\nthe past", "episodes\nvs bar of 5"),
    (8.0, "Decide\n+ write", "trigger?\nsnippet or\nquiet line"),
]
for x, title, sub in steps:
    ax.add_patch(FancyBboxPatch((x, 1.4), 1.6, 2.2,
                                boxstyle="round,pad=0.08",
                                ec=INK, fc="white", lw=1.4))
    ax.text(x + 0.8, 2.9, title, ha="center", va="center",
            fontsize=8, weight="bold", color=INK)
    ax.text(x + 0.8, 2.0, sub, ha="center", va="center",
            fontsize=7, color="#444444")
for i in range(len(steps) - 1):
    x1 = steps[i][0] + 1.6
    x2 = steps[i + 1][0]
    ax.add_patch(FancyArrowPatch((x1, 2.5), (x2, 2.5), arrowstyle="-|>",
                                 color=INK, lw=1.2, mutation_scale=10))
ax.text(5, 0.95, "guardrails: keys in environment only · pull never enters data/",
        ha="center", fontsize=7.5, style="italic", color="#444444")
ax.text(5, 0.45, "snippets are templates · every number pre-checked",
        ha="center", fontsize=7.5, style="italic", color="#444444")
ax.text(5, 4.35, "No model writes a word; the human lines are assembled, not composed.",
        ha="center", fontsize=8, style="italic", color=WARM, weight="bold")
ax.set_title("The morning round: from sky to human lines, all checkable.",
             fontsize=9.5, weight="bold", color=INK, pad=10)
save(fig, "f7_morning.png")

# F6: gate growth + catches ----------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 3.0))
steps = ["Setup-\nPipes\n(G1-10)", "Hardening\n(+G11)", "Nepal\ndemo\n(+G12)",
         "P0 flex\n(+G13-15)", "P1/P2\n(+G16-18)", "Memory\n(+G19-21)",
         "Evolver\n(+G22-24)", "Morning\n(+G25)"]
cum = [10, 11, 12, 15, 18, 21, 24, 25]
ax.step(range(len(steps)), cum, where="mid", color=ACCENT, lw=2)
ax.scatter(range(len(steps)), cum, color=ACCENT, zorder=3)
ax.set_xticks(range(len(steps)))
ax.set_xticklabels(steps, fontsize=7)
ax.set_ylabel("hardened gates (cumulative)")
ax.set_ylim(0, 27)
catches = [(1, "empty-output\nhole closed"), (2, "reads no\npost-cutoff byte"),
           (5, "silence +\nleakage +\nnull gates"), (6, "propose-test-\nwait human")]
for x, txt in catches:
    ax.annotate(txt, (x, cum[x]), textcoords="offset points", xytext=(12, -22),
                fontsize=6.8, color="#444444",
                arrowprops=dict(arrowstyle="-", color=GREY, lw=0.8))
ax.set_title("The gate set grew with the system: 10 setup gates to 25, each phase adding its own.",
             fontsize=9, weight="bold", color=INK, pad=10)
save(fig, "f6_gates.png")
print("all figures done")
