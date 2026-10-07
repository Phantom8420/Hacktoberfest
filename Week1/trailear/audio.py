"""Decode anything PyAV can read to mono float32 at the model's 32 kHz."""
from math import gcd

import numpy as np
from scipy.signal import resample_poly

SR = 32000


def resample(x, rate, sr=SR):
    if rate == sr:
        return x.astype("float32")
    g = gcd(sr, rate)
    return resample_poly(x, sr // g, rate // g).astype("float32")


def load(path, sr=SR, max_seconds=125):
    import av

    c = av.open(str(path))
    s = c.streams.audio[0]
    chunks, got = [], 0
    for pkt in c.demux(s):
        try:  # some Commons oggs carry a bad packet; drop it, keep the rest
            for f in pkt.decode():
                a = f.to_ndarray().astype("float32")
                if a.ndim == 2:
                    a = a.reshape(-1, f.layout.nb_channels).T if not f.format.is_planar else a
                    a = a.mean(0)
                chunks.append(a)
                got += a.shape[-1]
            if got > max_seconds * s.rate:
                break  # engine only reads two minutes anyway
        except Exception:
            continue
    if not chunks:
        raise ValueError(f"no decodable audio in {path}")
    x = np.concatenate(chunks)
    if np.abs(x).max() > 2:
        x = x / 32768.0
    return resample(x, s.rate, sr)
