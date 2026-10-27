import numpy as np

from spiritbox import ghosts, noise


def seg(text, **kw):
    return dict(start=0, end=1, text=text, lang="en", no_speech=0.1, logprob=-0.3, compression=1.2) | kw


def test_known_ghosts():
    assert ghosts.kind(seg("Thanks for watching!")) == "sign-off"
    assert ghosts.kind(seg("(water splashing)")) == "sound tag"
    assert ghosts.kind(seg("a little bit of a little bit of", compression=3.1)) == "repetition loop"
    assert ghosts.kind(seg("1.5 km de Rue", lang="fr")) == "wrong language"
    assert ghosts.kind(seg("Hello", no_speech=0.9, logprob=-1.4)) == "unsure audio"


def test_speech_passes():
    assert ghosts.kind(seg("Let's start with the numbers from last week.")) is None
    assert ghosts.kind(seg("Can you watch the build for me?")) is None


def test_repeated_line_is_a_loop():
    out = ghosts.flag([seg("I'm going to the next room."), seg("I'm going to the next room.")])
    assert [s["verdict"] for s in out] == ["real", "ghost"]


def test_noise_is_reproducible_and_in_range():
    for k in noise.KINDS:
        a = noise.make(k, 30, seed=3)
        assert len(a) == 30 * noise.SR and np.array_equal(a, noise.make(k, 30, seed=3))
        assert np.abs(a).max() <= 1
