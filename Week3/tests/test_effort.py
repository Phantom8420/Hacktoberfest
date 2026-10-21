import http.client
import io
import json
import random
import threading
from http.server import ThreadingHTTPServer

import pytest
from PIL import Image

from effort import gemma, judge, learn, log, plan, see, server


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
        assert abs(plan.make(items, budget)["score"] - round(b, 3)) < 1e-9  # small rooms get the exact plan


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


def jpeg(w=60, h=40):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "grey").save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def live(tmp_path):
    room = [item(1, "bed", 20, 4), item(2, "desk", 5, 2), item(3, "floor", 8, 3)]
    app = server.App(log_path=tmp_path / "runs.jsonl", look=lambda photo: [dict(i) for i in room],
                     verdict=lambda b, a, items: {"verdict": "tidier", "margin": 2, "gone": [2],
                                                  "mess_removed": 0.22, "after_items": []})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    server.Handler.app, server.Handler.port = app, srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], tmp_path / "runs.jsonl"
    srv.shutdown()


def call(port, method, path, body=None, ctype="application/json", host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = json.dumps(body).encode() if ctype == "application/json" and body is not None else body
    c.request(method, path, body=data, headers={"Content-Type": ctype, "Host": host or f"127.0.0.1:{port}"})
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}") if "json" in r.getheader("Content-Type", "") else r.read()


def test_server_full_run(live):
    port, path = live
    status, seen = call(port, "POST", "/api/see", jpeg(), "image/jpeg")
    assert status == 200 and len(seen["items"]) == 3
    status, p = call(port, "POST", "/api/plan", {"run": seen["run"], "budget": 15, "removed": [3]})
    assert status == 200 and [m["id"] for m in p["moves"]] == [2] and p["one"]["id"] == 2
    assert call(port, "POST", "/api/done", {"run": seen["run"], "item": 2, "actual_seconds": 12.5})[0] == 200
    status, v = call(port, "POST", f"/api/after?run={seen['run']}", jpeg(), "image/jpeg")
    assert status == 200 and v["verdict"] == "tidier"
    kinds = [r["kind"] for r in log.read(path)]
    assert kinds == ["see", "plan", "done", "after"]
    assert log.read(path)[1]["removed"] == [3]  # hallucinations are recorded
    assert "photo" not in json.dumps(log.read(path)[0]["items"])  # only a hash of the photo is kept
    status, f = call(port, "GET", "/api/factors")
    assert f["moves"] == 1 and f["factors"]["other"] > 1


def test_server_refuses_other_hosts_and_bad_input(live):
    port, _ = live
    assert call(port, "GET", "/api/factors", host="evil.example")[0] == 403
    assert call(port, "POST", "/api/see", b"not an image", "text/plain")[0] == 400
    assert call(port, "POST", "/api/plan", {"run": "nope", "budget": 10})[0] == 400
    assert call(port, "GET", "/../effort/server.py")[0] == 404
