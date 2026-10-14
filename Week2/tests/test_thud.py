import json

import numpy as np
import pytest

from thud import ledger as L
from thud import report, score, taps
from thud.demo import floor

PATTERN = [False] * 6 + [True] + [False] * 5 + [True, True] + [False] * 6


def test_finds_every_tap_once():
    found = taps.extract(floor(PATTERN))
    assert len(found) == len(PATTERN)
    assert all(abs(f["t"] - (0.3 + i * 0.6)) < 0.01 for i, f in enumerate(found))


def test_silence_has_no_taps():
    assert taps.extract(np.zeros(taps.SR, dtype="float32")) == []


def test_hollow_taps_ring_lower_and_longer():
    rows = taps.extract(floor(PATTERN))
    hol = [r for r, h in zip(rows, PATTERN) if h]
    sol = [r for r, h in zip(rows, PATTERN) if not h]
    assert min(r["low_ratio"] for r in hol) > max(r["low_ratio"] for r in sol)
    assert min(r["decay_ms"] for r in hol) > max(r["decay_ms"] for r in sol)


def test_suspicion_ranks_hollow_tiles_first():
    sus = score.suspicion(taps.extract(floor(PATTERN, seed=3)))
    top = sorted(range(len(sus)), key=lambda i: -sus[i])[:3]
    assert {i for i, h in enumerate(PATTERN) if h} == set(top)


def test_classify_needs_both_classes():
    rows = taps.extract(floor(PATTERN))
    with pytest.raises(ValueError):
        score.classify(rows, ["solid"] * len(rows))


def test_tabpfn_learns_a_floor_from_four_labels():
    pytest.importorskip("tabpfn")
    rows = taps.extract(floor(PATTERN, seed=7))
    labels = [None] * len(rows)
    labels[0] = labels[1] = "solid"
    labels[6] = labels[12] = "hollow"
    try:
        name, p = score.classify(rows, labels)
    except RuntimeError as e:
        pytest.skip(f"TabPFN weights not available: {e}")
    assert [x >= 0.5 for x in p] == PATTERN


def test_ledger_detects_edits(tmp_path):
    path = tmp_path / "l.jsonl"
    led = L.Ledger(path)
    led.seal({"room": "kitchen", "flagged": 2}, now=1)
    head = led.seal({"room": "hall", "flagged": 0}, now=2)["hash"]
    assert L.verify(path)[0]
    assert L.verify(path, anchor=head[:12])[0]
    lines = path.read_text().splitlines()
    e = json.loads(lines[0])
    e["body"]["flagged"] = 0
    path.write_text(json.dumps(e) + "\n" + lines[1] + "\n")
    ok, msg = L.verify(path)
    assert not ok and "entry 1" in msg


def test_report_falls_back_without_ollama(monkeypatch):
    monkeypatch.setattr(report, "OLLAMA", "http://127.0.0.1:9")
    insp = {"room": "Hall", "rows": 2, "cols": 2, "tiles": [
        {"r": 0, "c": 0, "tapped": True, "p_hollow": 0.9},
        {"r": 1, "c": 1, "tapped": True, "p_hollow": 0.1, "label": "hollow"}]}
    md, model = report.write(insp, [], timeout=2)
    assert model.startswith("template") and "A1: 90%" in md and "inspector: B2" in md


def test_model_cannot_invent_tiles_or_photos(monkeypatch):
    monkeypatch.setattr(report, "_chat", lambda *a: "## Summary\nSix tiles flagged.\n## Recommended next steps\n- Lift A1.")
    insp = {"room": "Hall", "rows": 1, "cols": 2, "tiles": [
        {"r": 0, "c": 0, "tapped": True, "p_hollow": 0.9}, {"r": 0, "c": 1, "tapped": True, "p_hollow": 0.1}]}
    md, model = report.write(insp, [])
    assert "- A1: 90% likely hollow" in md and "A2" not in md
    assert "## Photo findings\nNo photos attached." in md and md.endswith("- Lift A1.")
