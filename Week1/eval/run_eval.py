"""Measure verdicts and replay detection on an ESC-50 subset from fetch_esc50.py.

Usage: python eval/run_eval.py CLIPS_DIR [--no-replay]
Per-fold tables are printed so tuned folds (1-2) and untouched folds (3-5) stay separate.
"""
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trailear.audio import SR, load, resample  # noqa: E402
from trailear.fingerprint import best_match, phases  # noqa: E402

GRASS = ("TOUCHED_GRASS", "GRASS_PLUS_NOISE")
VERDICTS = ("TOUCHED_GRASS", "GRASS_PLUS_NOISE", "AMBIENT_NATURE", "INCONCLUSIVE", "HUMAN_MADE")


def verdict_tables(rows):
    for title, folds in (("all folds", (1, 2, 3, 4, 5)), ("folds 1-2 (rules tuned here)", (1, 2)),
                         ("folds 3-5 (untouched)", (3, 4, 5))):
        print(f"\n== {title}")
        print(f"{'group':8} {'n':>4}  " + "  ".join(f"{v[:9]:>9}" for v in VERDICTS))
        for g in ("life", "ambient", "human"):
            s = [r for _, r in rows if r["cls"] == g and r["fold"] in folds]
            c = collections.Counter(r["verdict"] for r in s)
            print(f"{g:8} {len(s):4}  " + "  ".join(f"{c[v]:9}" for v in VERDICTS))
    print("\nper category, folds 3-5: grass / ambient / inconclusive / human_made")
    cat = collections.defaultdict(collections.Counter)
    for _, r in rows:
        if r["fold"] >= 3:
            cat[(r["cls"], r["category"])][r["verdict"]] += 1
    for (g, c), v in sorted(cat.items()):
        print(f"  {g:8} {c:16} {v['TOUCHED_GRASS'] + v['GRASS_PLUS_NOISE']:2} {v['AMBIENT_NATURE']:2} "
              f"{v['INCONCLUSIVE']:2} {v['HUMAN_MADE']:2}")


rng = np.random.default_rng(0)


def room(x, rt60=0.35):
    n = int(rt60 * SR)
    ir = rng.normal(0, 1, n) * np.exp(-6.9 * np.arange(n) / n)
    ir[0] = 1.0
    return fftconvolve(x, ir / np.abs(ir).sum() * 3, mode="full")[:len(x)].astype("float32")


def noisy(x, snr_db):
    return x + rng.normal(0, x.std() * 10 ** (-snr_db / 20), x.shape).astype("float32")


def attacks(x):
    yield "gain x0.3", x * 0.3
    yield "22.05k round trip", resample(resample(x, SR, 22050), 22050, SR)
    yield "noise 20 dB", noisy(x, 20)
    yield "noise 10 dB", noisy(x, 10)
    yield "lowpass 4k", sosfilt(butter(4, 4000, fs=SR, output="sos"), x).astype("float32")
    yield "trim first 1.7 s", x[int(1.7 * SR):]
    yield "room + 15 dB noise", noisy(room(x), 15)


def replay_tables(d, fps, meta):
    print("\n== replay: same clip attacked (votes, share) vs different recordings")
    by = collections.defaultdict(list)
    for name, fp in fps.items():
        x = load(d / name)  # reloaded: holding 560 clips plus the model overran the RAM budget
        if np.abs(x).max() == 0:
            continue
        for a, y in attacks(x):
            by[a].append(best_match(fp, phases(y)))
    for a, v in by.items():
        vs = np.array([p[0] for p in v])
        print(f"  {a:20} n={len(v):3} votes min {vs.min():4} p5 {np.percentile(vs, 5):6.1f} median {np.median(vs):6.1f}")
    names = list(fps)
    pairs = {(i, j) for i in range(len(names)) for j in range(i + 1, len(names))
             if meta[names[i]]["src"] != meta[names[j]]["src"]}
    same_cat = [p for p in pairs if meta[names[p[0]]]["category"] == meta[names[p[1]]]["category"]]
    pairs = sorted(pairs)
    pick = {pairs[k] for k in rng.choice(len(pairs), min(30000, len(pairs)), replace=False)} | set(same_cat)
    neg = []
    for i, j in pick:
        neg.append(best_match(fps[names[i]], [fps[names[j]]]))
    nv = np.array([n[0] for n in neg])
    print(f"  different recordings: n={len(neg)} votes max {nv.max()} p99.9 {np.percentile(nv, 99.9):.1f} median {np.median(nv):.0f}")
    return by, nv


def main():
    from trailear.engine import Listener
    d = Path(sys.argv[1])
    lis = Listener()
    rows, fps, meta = [], {}, {}
    lat = []
    for m in json.load(open(d / "manifest.json")):
        x = load(d / m["file"])
        t = time.time()
        r = lis.listen(x)
        lat.append((time.time() - t) / r["windows"])
        rows.append((m["file"], {**m, "verdict": r["verdict"]}))
        fps[m["file"]], meta[m["file"]] = r["landmarks"], m
    verdict_tables(rows)
    print(f"\nlatency {np.mean(lat) * 1000:.0f} ms per 5 s window")
    del lis, r
    if "--no-replay" not in sys.argv:
        replay_tables(d, fps, meta)


if __name__ == "__main__":
    main()
