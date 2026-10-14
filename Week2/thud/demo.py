"""Synthetic coin taps for the demo floor and the tests. Not evidence that the method works on real
floors: it only checks the pipeline does what it claims on known input."""
import numpy as np

from .taps import SR


def tap(hollow, rng, gain=1.0):
    t = np.arange(int(0.12 * SR)) / SR
    click = rng.normal(0, 1, t.size) * np.exp(-t / 0.0006)
    y = 0.6 * click
    for f, tau in ((3200, 0.004), (5400, 0.003)):
        y += np.sin(2 * np.pi * f * rng.uniform(0.95, 1.05) * t) * np.exp(-t / tau)
    if hollow:  # a debonded tile is a plate over an air gap: one low mode that rings
        y += 1.4 * np.sin(2 * np.pi * rng.uniform(600, 900) * t) * np.exp(-t / 0.035)
    return gain * y


def floor(pattern, seed=0, spacing=0.6, noise=0.003):
    """pattern: list of bools (hollow?) in tap order. Returns float32 audio."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, noise, int((len(pattern) * spacing + 0.5) * SR))
    for i, h in enumerate(pattern):
        s = int((0.3 + i * spacing) * SR)
        y = tap(h, rng, gain=rng.uniform(0.4, 1.0))  # coin drops are never identical
        x[s:s + y.size] += y
    return x.astype("float32")
