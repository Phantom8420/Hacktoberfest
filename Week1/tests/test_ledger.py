import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trailear import fingerprint as fp  # noqa: E402
from trailear import ledger as L  # noqa: E402
from trailear.audio import SR  # noqa: E402


def tone_noise(seed, seconds=12):
    rng = np.random.default_rng(seed)
    t = np.arange(seconds * SR) / SR
    x = sum(np.sin(2 * np.pi * f * t * (1 + 0.3 * np.sin(2 * np.pi * r * t)))
            for f, r in zip(rng.uniform(800, 3500, 6), rng.uniform(0.2, 2, 6)))
    return (x + rng.normal(0, 0.3, t.shape)).astype("float32")


def result(x, verdict="TOUCHED_GRASS", score=80):
    ph = fp.phases(x)
    return dict(phases=ph, landmarks=ph[0], seconds=len(x) / SR, score=score, verdict=verdict,
                life=0.5, noise=0.1, species=[])


def test_chain_verifies_and_detects_edit(tmp_path):
    p = tmp_path / "l.jsonl"
    led = L.Ledger(p)
    led.seal(result(tone_noise(1)), "a" * 64, now=1)
    led.seal(result(tone_noise(2)), "b" * 64, now=2)
    assert L.verify(p)[0]

    lines = p.read_text().splitlines()
    e = json.loads(lines[0])
    e["body"]["score"] = 100
    lines[0] = json.dumps(e)
    p.write_text("\n".join(lines) + "\n")
    ok, msg = L.verify(p)
    assert not ok and "edited" in msg


def test_deleting_an_entry_breaks_chain(tmp_path):
    p = tmp_path / "l.jsonl"
    led = L.Ledger(p)
    for i in range(3):
        led.seal(result(tone_noise(i)), "c" * 64, now=i)
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:1] + lines[2:]) + "\n")
    assert not L.verify(p)[0]


def test_replay_is_caught_even_when_trimmed_and_quieter(tmp_path):
    led = L.Ledger(tmp_path / "l.jsonl")
    x = tone_noise(7, 20)
    first = led.seal(result(x), "d" * 64, now=1)
    assert first["body"]["verdict"] == "TOUCHED_GRASS"
    y = (x[int(1.7 * SR):] * 0.3).astype("float32")
    second = led.seal(result(y), "e" * 64, now=2)
    assert second["body"]["verdict"] == "REPLAY"
    assert second["body"]["replay_of"] == first["hash"]
    assert second["body"]["score"] == 0


def test_different_recording_is_not_a_replay(tmp_path):
    led = L.Ledger(tmp_path / "l.jsonl")
    led.seal(result(tone_noise(3, 20)), "f" * 64, now=1)
    other = led.seal(result(tone_noise(4, 20)), "0" * 64, now=2)
    assert other["body"]["verdict"] == "TOUCHED_GRASS"


def test_anchor_detects_full_rewrite(tmp_path):
    p = tmp_path / "l.jsonl"
    led = L.Ledger(p)
    led.seal(result(tone_noise(1)), "a" * 64, now=1)
    head = led.seal(result(tone_noise(2)), "b" * 64, now=2)["hash"]
    assert L.verify(p, head)[0]
    # forger rebuilds a self-consistent chain with a different score
    q = tmp_path / "forged.jsonl"
    forged = L.Ledger(q)
    forged.seal(result(tone_noise(1), score=100), "a" * 64, now=1)
    forged.seal(result(tone_noise(2)), "b" * 64, now=2)
    assert L.verify(q)[0] and not L.verify(q, head)[0]


def test_unrelated_recording_is_not_a_replay(tmp_path):
    led = L.Ledger(tmp_path / "l.jsonl")
    led.seal(result(tone_noise(1, 20)), "a" * 64, now=1)
    assert led.seal(result(tone_noise(2, 20)), "b" * 64, now=2)["body"]["verdict"] == "TOUCHED_GRASS"
