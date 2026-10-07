"""Shazam-style landmark fingerprint, used to catch someone replaying an old
recording. The mean Perch embedding was my first try; it fell to ~0.70 cosine
under added noise or a 4 kHz lowpass, no better than two unrelated clips.
Spectrogram peak pairs survive both because they only need the loudest
time-frequency points to stay put.

Matching is by offset voting: every shared hash votes for the time shift that
would line the two clips up, and a replay is many votes landing on one shift.
That stays reliable with far fewer surviving hashes than a plain set overlap.
"""
import base64

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.signal import stft

from .audio import SR

KEEP_MOD = 5    # keep ~1/5 of frequency pairs
FAN = 6
HOP = 512
MAX_S = 40      # seconds of audio fingerprinted


def landmarks(x, phase=0):
    """Return (hashes, frames), both uint32, for one STFT grid alignment."""
    x = x[phase:phase + MAX_S * SR]
    step = 10 * SR  # chunked so a two-minute clip doesn't eat the RAM
    cols = []
    for i in range(0, max(1, len(x) - 1024), step):
        _, _, Z = stft(x[i:i + step + 1024].astype("float32"), fs=SR, nperseg=1024, noverlap=1024 - HOP)
        cols.append(np.abs(Z[:256]).astype("float32"))
    S = np.log1p(np.concatenate(cols, axis=1) * 50)  # 0-4 kHz, where birds and traffic both live
    S = S - S.mean(axis=1, keepdims=True)       # gain and tilt drop out
    peaks = (S == maximum_filter(S, size=(21, 15))) & (S > np.percentile(S, 97))
    f, t = np.nonzero(peaks)
    order = np.argsort(t, kind="stable")
    f, t = f[order].astype("uint32"), t[order].astype("uint32")
    hs, ts = [], []
    for k in range(1, FAN + 1):
        if k >= len(t):
            break
        dt = t[k:] - t[:-k]
        ok = (t[k:] > t[:-k]) & (dt <= 63)
        hs.append((f[:-k][ok] << 14) | (f[k:][ok] << 6) | dt[ok])
        ts.append(t[:-k][ok])
    if not hs:
        return np.zeros(0, "uint32"), np.zeros(0, "uint32")
    h, t0 = np.concatenate(hs), np.concatenate(ts)
    # subsample on the frequency pair only, so every dt variant of a kept pair survives
    keep = (((h >> 6).astype("uint64") * 2654435761) >> 7) % KEEP_MOD == 0
    h, t0 = h[keep], t0[keep]
    key = np.unique((h.astype("uint64") << 32) | t0)
    return (key >> 32).astype("uint32"), (key & 0xFFFFFFFF).astype("uint32")


def phases(x):
    """Fingerprints at four sub-frame offsets. A copy trimmed by an arbitrary
    amount lands off the STFT grid; one of these lines back up with it."""
    return [landmarks(x, p) for p in range(0, HOP, HOP // 4)]


def votes(stored, query):
    """Most hashes agreeing on one time shift (+-1 frame)."""
    hs, ts = stored
    hq, tq = query
    if len(hs) == 0 or len(hq) == 0:
        return 0
    order = np.argsort(hs, kind="stable")
    hs, ts = hs[order], ts[order]
    lo = np.searchsorted(hs, hq, "left")
    cnt = np.searchsorted(hs, hq, "right") - lo
    tot = int(cnt.sum())
    if tot == 0:
        return 0
    qi = np.repeat(np.arange(len(hq)), cnt)
    si = np.repeat(lo - (np.cumsum(cnt) - cnt), cnt) + np.arange(tot)
    off = ts[si].astype("int64") - tq[qi].astype("int64")
    b = np.bincount(off - off.min())
    return int((b[:-1] + b[1:]).max()) if len(b) > 1 else int(b.max())


def best_match(stored, query_phases):
    """(votes, votes as a share of the smaller fingerprint)."""
    v = max(votes(stored, q) for q in query_phases)
    small = min(len(stored[0]), len(query_phases[0][0]))
    return v, (v / small if small else 0.0)


def pack(fp):
    h, t = fp
    return base64.b64encode(np.stack([h, t], 1).astype("<u4").tobytes()).decode()


def unpack(s):
    a = np.frombuffer(base64.b64decode(s), dtype="<u4").reshape(-1, 2)
    return a[:, 0].copy(), a[:, 1].copy()
