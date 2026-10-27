"""Things to listen to: generated noise (the same every run) and any audio file, as 16 kHz mono float32."""
import subprocess

import numpy as np

SR = 16000


def make(kind, seconds=30, seed=0):
    if seconds > 30:  # long noise in 30 s blocks with short crossfades: one big FFT can be more memory than we have
        fade = SR // 10
        out = make(kind, 30, seed)
        for k in range(1, int(np.ceil((seconds - 30) / 29.9)) + 1):
            nxt = make(kind, 30, seed * 1000 + k)
            w = np.linspace(0, 1, fade, dtype=np.float32)
            out = np.concatenate([out[:-fade], out[-fade:] * (1 - w) + nxt[:fade] * w, nxt[fade:]])
        return out[:int(seconds * SR)]
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    if kind == "silence":
        a = np.zeros(n)
    elif kind == "white":
        a = 0.05 * rng.standard_normal(n)
    elif kind in ("pink", "brown"):  # 1/f and 1/f^2 noise
        f = np.fft.rfftfreq(n, 1 / SR)
        f[0] = f[1]
        a = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / f ** (0.5 if kind == "pink" else 1), n)
        a *= (0.3 if kind == "pink" else 0.5) / np.abs(a).max()
    elif kind == "hum":  # mains hum and its harmonics, like a fridge or an old amp
        a = 0.1 * sum(np.sin(2 * np.pi * 50 * k * t) / k for k in range(1, 6)) + 0.01 * rng.standard_normal(n)
    elif kind == "fan":  # brown rumble with a slow wobble
        a = make("brown", seconds, seed) * (0.6 + 0.2 * np.sin(2 * np.pi * 0.3 * t))
    elif kind == "rain":  # pink hiss plus sparse drops
        a = 0.4 * make("pink", seconds, seed)
        for i in rng.integers(0, n - 400, int(seconds * 40)):
            a[i:i + 400] += rng.uniform(0.05, 0.3) * np.exp(-np.arange(400) / 60) * rng.standard_normal(400)
        a *= 0.5 / np.abs(a).max()  # drops pile up; keep the loudest under clipping
    else:
        raise ValueError(f"unknown noise: {kind}")
    return a.astype(np.float32)


KINDS = ("silence", "white", "pink", "brown", "hum", "fan", "rain")


def load(path):
    """Any audio or video file ffmpeg can read."""
    out = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).copy()


def wav(a):
    """16-bit wav bytes, for saving a recording or sending it to a browser."""
    import io
    import wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    return b.getvalue()
