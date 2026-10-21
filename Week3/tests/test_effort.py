import io
import random

from PIL import Image

from effort import gemma, judge, learn, log, plan, see


def test_clean_strips_gps_and_shrinks():
    img = Image.new("RGB", (4000, 3000), "white")
    exif = Image.Exif()
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPSInfo: latitude
    exif[0x0112] = 1
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert Image.open(buf).getexif()  # the fixture really has EXIF

    out = Image.open(io.BytesIO(gemma.clean(buf.getvalue())))
    assert not out.getexif()
    assert max(out.size) == gemma.SIDE


def test_clean_applies_rotation():
    img = Image.new("RGB", (400, 200))
    exif = Image.Exif()
    exif[0x0112] = 6  # phone held upright: stored sideways
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(gemma.clean(buf.getvalue()))).size == (200, 400)


def item(n, zone, secs, mess):
    return {"id": n, "what": f"thing {n}", "zone": zone, "move_to": "other", "est_seconds": secs, "mess": mess}


def test_empty_budget_and_too_expensive():
    items = [item(1, "desk", 10, 3), item(2, "bed", 500, 5)]
    assert plan.make(items, 0)["moves"] == []
    assert all(m["id"] != 2 for m in plan.make(items, 100)["moves"])


def test_diminishing_returns_spreads_across_zones():
    items = [item(1, "desk", 10, 3), item(2, "desk", 10, 3), item(3, "bed", 10, 3)]
    zones = {m["zone"] for m in plan.make(items, 20)["moves"]}
    assert zones == {"desk", "bed"}


def test_single_big_item_beats_greedy_when_better():
    # greedy grabs the cheap crumb first and then can't afford the big one
    items = [item(1, "floor", 1, 1), item(2, "bed", 100, 5)]
    assert [m["id"] for m in plan.greedy(items, 100)] == [2]


def test_exact_never_worse_and_greedy_within_guarantee():
    rng = random.Random(7)
    for _ in range(200):
        items = [item(i, rng.choice("abc"), rng.randint(2, 60), rng.randint(1, 5)) for i in range(rng.randint(1, 8))]
        budget = rng.randint(5, 120)
        g, b = plan.score(plan.greedy(items, budget)), plan.score(plan.best(items, budget))
        assert b >= g - 1e-9
        assert g >= (1 - 1 / 2.718281828) / 2 * b - 1e-9


def test_order_groups_zones():
    moves = plan.order([item(1, "desk", 5, 5), item(2, "bed", 5, 1), item(3, "desk", 50, 1)])
    zones = [m["zone"] for m in moves]
    assert zones == ["desk", "desk", "bed"]


def test_tidy_clamps_and_dedupes():
    raw = {"items": [{"what": "Shirt ", "zone": "Bed", "move_to": "attic", "est_seconds": 9999, "mess": 0},
                     {"what": "shirt", "zone": "bed", "move_to": "laundry", "est_seconds": 5, "mess": 3},
                     {"what": "cup", "zone": "desk", "move_to": "sink", "est_seconds": "x", "mess": 2}]}
    out = see.tidy(raw)
    assert [(i["what"], i["move_to"], i["est_seconds"], i["mess"]) for i in out] == [
        ("shirt", "other", 300, 1), ("cup", "sink", 30, 2)]
    assert see.tidy("garbage") == []


def test_learn_starts_neutral_and_converges():
    assert learn.factors([]) == {}
    one = learn.factors([{"move_to": "bin", "est_seconds": 5, "actual_seconds": 50}])
    assert 1 < one["bin"] < 10  # one outlier only moves it partway
    many = learn.factors([{"move_to": "bin", "est_seconds": 5, "actual_seconds": 15}] * 200)
    assert abs(many["bin"] - 3) < 0.05
    costed = learn.apply([item(1, "desk", 10, 3) | {"move_to": "bin"}, item(2, "desk", 10, 3)], many)
    assert [c["cost"] for c in costed] == [30, 10]


def test_log_roundtrip(tmp_path):
    p = tmp_path / "runs.jsonl"
    log.add("done", path=p, move_to="bin", est_seconds=5, actual_seconds=9)
    log.add("see", path=p, photo=log.photo_id(b"x"))
    assert [r["kind"] for r in log.read(p)] == ["done", "see"]
    assert len(log.done_moves(p)) == 1
    assert log.read(tmp_path / "missing.jsonl") == []


def test_judge_removed_and_swap(monkeypatch):
    before = [item(1, "bed", 10, 4) | {"what": "pile of shirts"}, item(2, "desk", 5, 2) | {"what": "mug"}]
    after = [item(1, "bed", 10, 4) | {"what": "pile of shirt"}]
    assert [g["id"] for g in judge.removed(before, after)] == [2]

    answers = iter([{"tidier": "B", "margin": 2}, {"tidier": "A", "margin": 1}])
    monkeypatch.setattr(judge.gemma, "chat", lambda *a, **k: next(answers))
    img = io.BytesIO(); Image.new("RGB", (40, 30)).save(img, "JPEG")
    assert judge.compare(img.getvalue(), img.getvalue())["verdict"] == "tidier"

    biased = iter([{"tidier": "A", "margin": 2}, {"tidier": "A", "margin": 2}])  # always "the first one"
    monkeypatch.setattr(judge.gemma, "chat", lambda *a, **k: next(biased))
    assert judge.compare(img.getvalue(), img.getvalue())["verdict"] == "unclear"
