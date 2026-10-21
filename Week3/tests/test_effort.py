import io
import random

from PIL import Image

from effort import gemma, plan, see


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
