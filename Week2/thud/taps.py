"""Find coin taps in a recording and describe each one with a few numbers.

Every feature is a frequency or a ratio, never a loudness, so a harder or
softer drop moves the row less than the floor under the tile does.
"""
import numpy as np

SR = 32000
PRE = int(0.002 * SR)       # keep 2 ms before the onset
WIN = int(0.120 * SR)       # a tap rings out well inside 120 ms on tile
GAP = int(0.250 * SR)       # two taps closer than this are one tap
FEATURES = ["peak_hz", "centroid_hz", "rolloff_hz", "low_ratio", "decay_ms", "ring_ratio", "flatness"]


def _envelope(x):
    k = np.ones(int(0.001 * SR)) / int(0.001 * SR)
    return np.convolve(np.abs(x), k, mode="same")


def detect(x):
    """Sample index of each tap onset."""
    x = np.asarray(x, dtype="float32")
    if x.size < WIN:
        return []
    env = _envelope(x)
    floor = np.median(env) + 1e-9
    peak = env.max()
    # shortcut: fixed thresholds, fine for a quiet room; noisy sites may need a per-site setting
    thr = max(floor * 8, peak * 0.12)
    onsets, i = [], 0
    above = np.flatnonzero(env > thr)
    for i in above:
        if not onsets or i - onsets[-1] > GAP:
            if i + WIN <= x.size:
                onsets.append(int(i))
    return onsets


def describe(seg):
    """Seven numbers for one tap segment (starting PRE samples before onset)."""
    seg = seg.astype("float64") - seg.mean()
    spec = np.abs(np.fft.rfft(seg * np.hanning(seg.size))) ** 2
    hz = np.fft.rfftfreq(seg.size, 1 / SR)
    band = (hz >= 60) & (hz <= 12000)
    p, f = spec[band] + 1e-18, hz[band]
    total = p.sum()
    cum = np.cumsum(p) / total
    env = _envelope(seg)
    top = int(env.argmax())
    below = np.flatnonzero(env[top:] < env[top] * 0.1)  # -20 dB
    head = int(0.030 * SR)
    return {
        "peak_hz": float(f[p.argmax()]),
        "centroid_hz": float((f * p).sum() / total),
        "rolloff_hz": float(f[np.searchsorted(cum, 0.85)]),
        "low_ratio": float(p[f < 1000].sum() / total),
        "decay_ms": float((below[0] if below.size else env.size - top) / SR * 1000),
        "ring_ratio": float((seg[head:] ** 2).sum() / ((seg[:head] ** 2).sum() + 1e-18)),
        "flatness": float(np.exp(np.log(p).mean()) / p.mean()),
    }


def extract(x):
    """[{t, ...features}] for every tap found in x (mono float32 at SR)."""
    x = np.asarray(x, dtype="float32")
    out = []
    for o in detect(x):
        s = max(0, o - PRE)
        out.append({"t": round(o / SR, 3), **{k: round(v, 4) for k, v in describe(x[s:s + WIN]).items()}})
    return out
