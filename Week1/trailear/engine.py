"""Perch 2.0 inference and the Grass Score."""
import os
from pathlib import Path

import numpy as np

from .audio import SR
from .fingerprint import phases
from .labels import group_indices, load_labels

WIN = 5 * SR
MAX_WINDOWS = 24  # two minutes is plenty of evidence
# Perch logits are uncalibrated: on my first 12 clips noise-level guesses sat
# at 6-9 and real detections at 12+. Thresholds below were fit on those clips.
CONFIDENT = 12.0
M_LO, M_HI = 2.0, 8.0   # margin ramp for the 0-100 score
GRASS_MARGIN = 3.0
NOISY_BAR = 6.5      # grass plus this much human sound is GRASS_PLUS_NOISE
# First ESC-50 run (thresholds frozen from the earlier Wikimedia clips) stamped 85/140
# weather/water clips HUMAN_MADE: rain, wind and thunder light up catch-all labels like
# "Vehicle" and "Domestic sounds". The two rules below were fit on ESC-50 folds 1-2 only;
# folds 3-5 are the untouched check (see README).
AMBIENT_NH = 0.5     # mean(nature - human) at or above this, with no life: AMBIENT_NATURE
HUMAN_BAR = 8.5
HUMAN_NH = -3.5      # HUMAN_MADE needs strong human sound AND nature far below it

DEFAULT_MODEL = Path(os.environ.get(
    "TRAILEAR_MODEL", Path(__file__).resolve().parent.parent / "models" / "perch_v2.onnx"))


class Listener:
    def __init__(self, model=DEFAULT_MODEL):
        import onnxruntime as ort

        if not Path(model).exists():
            raise FileNotFoundError(f"{model} missing, see README for the download")
        so = ort.SessionOptions()
        so.enable_mem_pattern = False  # keeps peak RAM down on small machines
        self.sess = ort.InferenceSession(str(model), so, providers=["CPUExecutionProvider"])
        self.labels = load_labels()
        self.idx = group_indices(self.labels)

    def windows(self, x):
        if len(x) < WIN:
            x = np.pad(x, (0, WIN - len(x)))
        n = max(1, min(MAX_WINDOWS, len(x) // WIN))
        return [x[i * WIN:(i + 1) * WIN] for i in range(n)]

    def listen(self, x):
        """Return the full evidence dict for a mono 32 kHz clip."""
        wins = self.windows(x)
        per = []
        for w in wins:
            (logits,) = self.sess.run(["label"], {"inputs": w[None].astype("float32")})
            lg = logits[0]
            g = {k: lg[v] for k, v in self.idx.items()}
            sp = int(np.argmax(g["species"]))
            per.append({
                "species": self.labels[self.idx["species"][sp]],
                "species_logit": round(float(g["species"][sp]), 2),
                "wild": round(float(g["wild"].max()), 2),
                "nature": round(float(g["nature"].max()), 2),
                "human": round(float(g["human"].max()), 2),
                "human_label": self.labels[self.idx["human"][int(np.argmax(g["human"]))]],
                "_all": lg,
            })
        res = summarize(per, self.labels, len(x) / SR)
        res["phases"] = phases(x)
        res["landmarks"] = res["phases"][0]
        return res


def summarize(per, labels, seconds):
    # The margin (best living-thing logit minus best human-made logit) separated
    # my clips far better than either alone: it survives uncalibrated logits.
    margins = [max(p["species_logit"], p["wild"] + 1.5) - p["human"] for p in per]
    m = float(np.mean(margins))
    hum = float(np.mean([p["human"] for p in per]))
    life = float(np.mean([np.clip((x - M_LO) / (M_HI - M_LO), 0, 1) for x in margins]))

    found = {}  # species clearing the confident bar in any window
    for p in per:
        lg = p["_all"]
        for i in np.where(lg >= CONFIDENT)[0]:
            if " " in labels[i]:
                found[labels[i]] = max(found.get(labels[i], 0), float(lg[i]))
    species = sorted(found.items(), key=lambda kv: -kv[1])

    nh = float(np.mean([p["nature"] - p["human"] for p in per]))
    if m >= GRASS_MARGIN and hum < NOISY_BAR:
        verdict = "TOUCHED_GRASS"
    elif m >= GRASS_MARGIN:
        verdict = "GRASS_PLUS_NOISE"
    elif nh >= AMBIENT_NH:
        verdict = "AMBIENT_NATURE"  # weather or water, nothing alive: not proof of a walk
    elif hum >= HUMAN_BAR and nh <= HUMAN_NH and m < 0:
        verdict = "HUMAN_MADE"
    else:
        verdict = "INCONCLUSIVE"  # silence, wind and thin choruses end up here
    score = round(100 * life) if verdict in ("TOUCHED_GRASS", "GRASS_PLUS_NOISE") else 0
    for p in per:
        p.pop("_all")
    return {
        "seconds": round(seconds, 1),
        "windows": len(per),
        "margin": round(m, 2),
        "nature_gap": round(nh, 2),
        "life": round(life, 3),
        "noise": round(hum, 2),
        "score": score,
        "verdict": verdict,
        "species": [{"name": n, "logit": round(v, 1)} for n, v in species[:8]],
        "per_window": per,
    }
