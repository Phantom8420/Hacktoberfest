"""Charts for the README from eval/results/*.json and runs.jsonl. Skips any chart whose data isn't there yet.

    python eval/charts.py
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from effort import log  # noqa: E402

RES = ROOT / "eval" / "results"
OUT = ROOT / "eval" / "charts"
INK, MUTED, MOSS, GREY = "#1d2a23", "#6b7c72", "#3f8f55", "#b8c4bc"

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print("wrote", name)


def solver():
    p = RES / "solver.json"
    if not p.exists():
        return
    r = json.loads(p.read_text())["random"]["ratios"]
    # most cases sit at exactly 1.0, so show every case sorted worst-first instead of a histogram
    fig, ax = plt.subplots(figsize=(6, 3))
    pct = [100 * i / (len(r) - 1) for i in range(len(r))]
    ax.plot(pct, sorted(x[2] for x in r), color=GREY, lw=2, label="biggest mess first")
    ax.plot(pct, sorted(x[1] for x in r), color=MOSS, lw=2, label="Effort Budget (greedy)")
    ax.set_xlabel(f"% of {len(r):,} random rooms × budgets, worst first")
    ax.set_ylabel("share of best possible")
    ax.set_xlim(0, 40)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "solver")


def stability():
    p = RES / "stability.json"
    if not p.exists():
        return
    s = json.loads(p.read_text())["scenes"]
    fig, ax = plt.subplots(figsize=(6, .35 * len(s) + 1))
    names = [x["scene"].replace("_", " ")[:28] for x in s]
    loose = [sum(x["jaccard_loose"]) / len(x["jaccard_loose"]) for x in s]
    strict = [sum(x["jaccard_strict"]) / len(x["jaccard_strict"]) for x in s]
    ax.barh(names, loose, color=GREY, label="same name")
    ax.barh(names, strict, color=MOSS, label="same name and zone")
    ax.set_xlim(0, 1)
    ax.set_xlabel("overlap of items between retakes (Jaccard)")
    ax.invert_yaxis()
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1), ncol=2)
    save(fig, "stability")


def calibration():
    done = log.done_moves() if log.PATH.exists() else []
    if len(done) < 3:
        return
    fig, ax = plt.subplots(figsize=(4.5, 4))
    est = [r["est_seconds"] for r in done]
    act = [r["actual_seconds"] for r in done]
    top = max(est + act) * 1.1
    ax.plot([0, top], [0, top], color=GREY, lw=1)
    ax.scatter(est, act, color=MOSS, s=22)
    ax.set_xlabel("Gemma's guess (s)")
    ax.set_ylabel("what it actually took (s)")
    save(fig, "calibration")


if __name__ == "__main__":
    solver()
    stability()
    calibration()
