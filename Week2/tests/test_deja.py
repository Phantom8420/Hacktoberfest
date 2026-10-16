import http.client
import io
import json
import sqlite3
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from deja import ask, capture, server, voice, when
from deja.scrub import MASK, scrub
from deja.store import Store

WED = datetime(2026, 10, 14, 15, 30)  # a Wednesday afternoon


@pytest.mark.parametrize("line", [
    "OPENAI_API_KEY=sk-proj-8f3k2LmQ9xT4vB7nR1wZ5cY0",
    "token: ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z",
    "password = hunter2",
    "Card 4111 1111 1111 1111 exp 09/29",
    "Your verification code is 482913",
    "AKIAIOSFODNN7EXAMPLE",
    "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
])
def test_scrub_hides_secrets(line):
    clean, hit = scrub(line)
    assert hit and MASK in clean


@pytest.mark.parametrize("line", [
    "Hotel Mirador - 4 nights from 212 per night",
    "commit 3f9a1c2e8b7d6a5f4e3d2c1b0a9f8e7d6c5b4a39",  # lowercase hex hash is not a secret
    "Order 1234 5678 shipped",                        # fails Luhn
    "Meeting at 10:30 in room 4021",
])
def test_scrub_leaves_ordinary_text(line):
    assert scrub(line) == (line, False)


def test_past_windows():
    s, e, rest = when.past("what was that hotel I looked at last tuesday", WED)
    assert (s, e) == (datetime(2026, 10, 13), datetime(2026, 10, 14)) and "tuesday" not in rest
    s, e, _ = when.past("the error I saw this morning", WED)
    assert (s.hour, e.hour, s.day) == (6, 12, 14)
    s, e, _ = when.past("this is the thing I saw yesterday", WED)
    assert s == datetime(2026, 10, 13)
    s, e, _ = when.past("last wednesday", WED)
    assert s == datetime(2026, 10, 7)
    s, e, _ = when.past("an hour ago", WED)
    assert s < datetime(2026, 10, 14, 14, 30) < e
    assert when.past("that recipe with lemon", WED)[:2] == (None, None)


def test_due_times():
    assert when.due("call the dentist tomorrow at 5", WED)[0] == datetime(2026, 10, 15, 17)
    assert when.due("send the invoice on friday", WED)[0] == datetime(2026, 10, 16, 9)
    assert when.due("stretch in 20 minutes", WED)[0] == datetime(2026, 10, 14, 15, 50)
    assert when.due("ring Sam at 9am", WED)[0] == datetime(2026, 10, 15, 9)  # 9am already passed today
    d, rest = when.due("buy milk", WED)
    assert d is None and rest == "buy milk"


def test_route():
    assert voice.route("Remind me to call the dentist tomorrow")[:2] == ("note", "reminder")
    assert voice.route("remember to buy milk")[:2] == ("note", "todo")
    assert voice.route("Note that the wifi password is on the fridge")[:2] == ("note", "note")
    assert voice.route("what was that hotel I saw on tuesday")[0] == "ask"


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path)
    now = time.time()
    s.add_frame(now - 3600, "chrome", "Hotel Mirador - Booking", "a.jpg", "Hotel Mirador\n4 nights from 212 per night")
    s.add_frame(now - 60, "code", "orders.py", "b.jpg", "ConnectionError: timeout after 30s in fetch_orders()")
    return s


def test_search_and_forget(store):
    hits = store.search(ask.terms("which hotel was it"))
    assert hits[0]["title"].startswith("Hotel Mirador")
    assert store.search(["timeout"])[0]["app"] == "code"
    assert store.search(ask.terms("what error did I get in orders.py"))[0]["app"] == "code"
    assert store.forget(since=time.time() - 300) == 1
    assert store.search(["timeout"]) == []


def test_nothing_readable_on_disk(store):
    store.add_note("The spare key is with Sam", "note")
    store.put_image("x.jpg", b"\xff\xd8 Mirador jpeg")
    disk = b"".join(p.read_bytes() for p in store.home.rglob("*") if p.is_file())
    for secret in (b"Mirador", b"ConnectionError", b"spare key", b"orders.py", b"chrome"):
        assert secret not in disk
    assert store.image("x.jpg") == b"\xff\xd8 Mirador jpeg"
    assert store.search(["nnectionErr"])[0]["app"] == "code"  # substring search still works


def test_tampered_image_is_refused(store):
    store.put_image("y.jpg", b"jpeg")
    p = store._img("y.jpg")
    p.write_bytes(p.read_bytes()[:-1] + b"\0")
    with pytest.raises(ValueError):
        store.image("y.jpg")


def test_old_plaintext_store_is_encrypted_and_removed(tmp_path):
    old = sqlite3.connect(tmp_path / "deja.db")
    old.executescript("create table frames(id integer primary key, t real, app text, title text, image text, text text);"
                      "create table notes(id integer primary key, t real, text text, kind text, due real, done integer, fired integer);")
    old.execute("insert into frames values (1, 1.0, 'chrome', 'Hotel Mirador', 'd/a.jpg', 'sea view')")
    old.execute("insert into notes values (1, 1.0, 'Call the dentist', 'todo', null, 0, 0)")
    old.commit()
    old.close()
    (tmp_path / "frames" / "d").mkdir(parents=True)
    (tmp_path / "frames" / "d" / "a.jpg").write_bytes(b"jpeg")
    s = Store(tmp_path)
    assert not (tmp_path / "deja.db").exists() and not (tmp_path / "frames" / "d" / "a.jpg").exists()
    assert s.search(["sea view"])[0]["title"] == "Hotel Mirador" and s.image("d/a.jpg") == b"jpeg"
    assert s.notes()[0]["text"] == "Call the dentist"


def test_answer_with_an_invented_number_is_dropped():
    hits = [{"title": "Casa Lumen", "text": "4 nights from 164 per night"}]
    assert ask.grounded("Casa Lumen was 164 per night.", hits)
    assert not ask.grounded("Casa Lumen cost $404 per night.", hits)


def test_padding_and_refusals_are_tidied():
    assert ask.tidy("I understand you're asking about the hotel. It was Hotel Mirador.") == "It was Hotel Mirador."
    assert ask.tidy("I couldn't find that.") is None
    assert ask.tidy("Gate 14.") == "Gate 14."
    assert ask.tidy("Lena: They are in Drive, under Brand.") == "They are in Drive, under Brand."


def test_related_words_widen_the_search(store, monkeypatch):
    monkeypatch.setattr(ask, "_chat", lambda system, user, timeout: (
        "price, nights, booking" if system == ask.EXPAND else "It was 212 per night [1]."))
    out = ask.ask(store, "how expensive was that place")
    assert out["hits"][0]["title"].startswith("Hotel Mirador") and out["answer"] == "It was 212 per night."


def test_ask_without_model_still_returns_evidence(store):
    out = ask.ask(store, "what was that hotel", use_model=False)
    assert out["hits"][0]["title"].startswith("Hotel Mirador") and out["answer"] is None


def test_ocr_paints_over_secret_lines(tmp_path):
    im = Image.new("RGB", (1400, 300), "white")
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype("arial.ttf", 30)
    d.text((40, 40), "Hotel Mirador from 212 per night", fill="black", font=f)
    d.text((40, 160), "api_key = sk-proj-8f3k2LmQ9xT4vB7nR1wZ5cY0", fill="black", font=f)
    bgr = np.asarray(im)[:, :, ::-1].copy()
    text, boxes, secret = capture.read(capture.ocr_engine(), bgr)
    assert "Mirador" in text and "sk-proj" not in text and secret
    s = Store(tmp_path)
    saved = np.asarray(Image.open(io.BytesIO(s.image(capture.save_frame(bgr, s, time.time(), boxes, secret)))))
    box = np.asarray(boxes[secret[0]])
    (x0, y0), (x1, y1) = box.min(0).astype(int) + 2, box.max(0).astype(int) - 2
    assert y0 > 120 and saved[y0:y1, x0:x1].max() < 30  # the key's line is solid black
    assert saved[40:80, 40:400].min() < 100              # the hotel line is still readable



def test_ocr_that_cannot_start_is_reported(store, monkeypatch):
    def fail():
        raise MemoryError("bad allocation")
    monkeypatch.setattr(capture, "ocr_engine", fail)
    rec = capture.Recorder(store, capture.Settings(store.home / "settings.json"))
    rec._ocr_loop()  # returns instead of dying silently
    assert rec.state.startswith("error") and "bad allocation" in rec.ocr_error

@pytest.fixture
def api(store):
    app = server.App(store, capture.Settings(store.home / "settings.json"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    server.Handler.app, server.Handler.port = app, srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port
    srv.shutdown()


def call(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port)
    h = {"Host": f"127.0.0.1:{port}", **(headers or {})}
    c.request(method, path, body, h)
    r = c.getresponse()
    return r.status, r.read()


def test_server_refuses_other_sites(api):
    assert call(api, "GET", "/api/timeline", headers={"Host": "evil.example:80"})[0] == 403
    assert call(api, "GET", "/api/timeline", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
    body = json.dumps({"all": True})
    assert call(api, "POST", "/api/forget", body, {"Content-Type": "text/plain"})[0] == 400
    assert call(api, "GET", "/frames/../deja.db")[0] == 404


def test_server_keeps_a_spoken_reminder(api):
    status, raw = call(api, "POST", "/api/ask", json.dumps({"text": "remind me to call the dentist tomorrow at 5"}),
                       {"Content-Type": "application/json"})
    note = json.loads(raw)["note"]
    assert status == 200 and note["kind"] == "reminder" and note["text"] == "Call the dentist"


def test_whisper_hears_a_question(tmp_path):
    import subprocess
    wav = tmp_path / "q.wav"
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                    f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('Remind me to water the plants tomorrow'); $s.Dispose()"],
                   check=True, capture_output=True)
    text = voice.transcribe(wav.read_bytes())
    assert "water the plants" in text.lower()
    assert voice.route(text)[:2] == ("note", "reminder")


def test_public_demo_is_read_only(tmp_path):
    from deja.demo import seed
    s = Store(tmp_path)
    assert seed(s) > 0 and seed(s) == 0  # seeds once
    app = server.App(s, capture.Settings(tmp_path / "settings.json"), public=True)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    server.Handler.app, server.Handler.port = app, srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        port, j = srv.server_port, {"Content-Type": "application/json"}
        assert call(port, "GET", "/api/status", headers={"Host": "deja.hf.space"})[0] == 200
        assert call(port, "POST", "/api/forget", json.dumps({"all": True}), j)[0] == 403
        notes = len(s.notes())
        status, raw = call(port, "POST", "/api/ask", json.dumps({"text": "remind me to stretch in 20 minutes"}), j)
        assert status == 200 and json.loads(raw)["note"]["kind"] == "reminder" and len(s.notes()) == notes
        assert s.search(ask.terms("which hotel had a sea view"))[0]["title"].startswith("Hotel Mirador")
    finally:
        srv.shutdown()
