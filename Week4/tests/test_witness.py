from spiritbox import witness


def test_flag_rules_first_then_gemma_on_suspects(monkeypatch):
    asked = []
    monkeypatch.setattr(witness, "judge", lambda segs, i, model: asked.append(i) or
                        {"verdict": "ghost", "kind": "echo", "reason": "said earlier"})
    segs = [{"start": 0, "end": 2, "text": "Thanks for watching.", "no_speech": 0.1, "logprob": -0.2},
            {"start": 3, "end": 5, "text": "The build broke.", "no_speech": 0.1, "logprob": -0.2},
            {"start": 40, "end": 42, "text": "The build broke again.", "no_speech": 0.8, "logprob": -0.9}]
    out = witness.flag(segs)
    assert [s["verdict"] for s in out] == ["ghost", "real", "ghost"]
    assert out[0]["kind"] == "sign-off" and asked == [2]  # only the doubted line went to Gemma
