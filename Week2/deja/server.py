"""The local web app. It listens on 127.0.0.1 only, and refuses anything sent by
another website (wrong Host header, cross-site fetch, or a form post), because
what it serves is a record of your screen.
"""
import json
import mimetypes
import re
import threading
import time
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import ask, voice, when
from .notify import toast

WEB = Path(__file__).parent / "web"
FRAME = re.compile(r"^/frames/(\d{4}-\d{2}-\d{2}/\d{6}_\d{3}\.jpg)$")
MAX_BODY = 25 * 2**20
DEMO_OK = ("/api/ask", "/api/voice")  # the only writes a public demo accepts


class App:
    def __init__(self, store, settings, recorder=None, public=False):
        self.store, self.settings, self.recorder, self.public = store, settings, recorder, public
        self.hotkeys = []

    def keep(self, text, kind):
        due, body = when.due(text)
        if kind == "reminder" and due is None:
            kind = "todo"
        if self.public:  # strangers share one demo: show what would be kept, keep nothing
            return {"id": None, "text": body or text, "kind": kind, "due": due and due.timestamp()}
        nid = self.store.add_note(body or text, kind, due and due.timestamp())
        return {"id": nid, "text": body or text, "kind": kind, "due": due and due.timestamp()}

    def forget_recent(self, minutes=5):
        return self.store.forget(since=time.time() - minutes * 60)

    def toggle_pause(self):
        self.settings.update({"paused": not self.settings.paused})

    def reminders(self):
        while True:
            for n in self.store.due_now():
                self.store.mark_fired(n["id"])
                try:
                    toast("Déjà reminder", n["text"])
                except Exception:
                    pass
            time.sleep(20)


class Handler(BaseHTTPRequestHandler):
    app: App = None
    port = 0

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", cache="no-store"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _trusted(self):
        host = self.headers.get("Host", "")
        # DNS rebinding: some other site's name pointed at 127.0.0.1. A public demo holds only sample screens.
        if not self.app.public and host not in (f"127.0.0.1:{self.port}", f"localhost:{self.port}"):
            return False
        return self.headers.get("Sec-Fetch-Site", "same-origin") in ("same-origin", "none")

    def _body(self, kind):
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip()
        if kind == "json" and ctype != "application/json":
            raise ValueError("send application/json")
        if kind == "audio" and not ctype.startswith("audio/"):
            raise ValueError("send audio")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("too large")
        raw = self.rfile.read(n)
        return json.loads(raw or b"{}") if kind == "json" else raw

    def do_GET(self):
        if not self._trusted():
            return self._send(403, {"error": "forbidden"})
        try:
            self._get()
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        if not self._trusted():
            return self._send(403, {"error": "forbidden"})
        try:
            self._post()
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def _get(self):
        url = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        a = self.app
        if url.path == "/api/status":
            r = a.recorder
            return self._send(200, {**a.store.stats(), "state": r.state if r else "not recording",
                                    "settings": a.settings.dict(), "gemma": ask.gemma_ready(),
                                    "gemma_model": ask.MODEL, "whisper_model": voice.MODEL,
                                    "hotkeys": a.hotkeys, "public": a.public})
        if url.path == "/api/timeline":
            day = datetime.strptime(q["day"], "%Y-%m-%d") if q.get("day") else datetime.now()
            start = datetime(day.year, day.month, day.day).timestamp()
            return self._send(200, {"day": time.strftime("%Y-%m-%d", time.localtime(start)),
                                    "frames": a.store.timeline(start, start + 86400, int(q.get("limit", 400)))})
        if url.path == "/api/frame":
            f = a.store.frame(int(q["id"]))
            return self._send(200 if f else 404, f or {"error": "gone"})
        if url.path == "/api/notes":
            return self._send(200, {"notes": a.store.notes(q.get("all") == "1")})
        m = FRAME.match(url.path)
        if m:
            p = a.store.home / "frames" / m.group(1)
            return self._send(200, p.read_bytes(), "image/jpeg", "private, max-age=86400") if p.exists() \
                else self._send(404, {"error": "gone"})
        name = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
        p = (WEB / name).resolve()
        if WEB.resolve() in p.parents and p.is_file():
            return self._send(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream",
                              "no-cache")
        self._send(404, {"error": "not found"})

    def _post(self):
        a, path = self.app, urllib.parse.urlsplit(self.path).path
        if a.public and path not in DEMO_OK:
            return self._send(403, {"error": "this is a read-only demo"})
        if path == "/api/voice":
            text = voice.transcribe(self._body("audio"))
            if not text:
                return self._send(200, {"text": "", "intent": "none"})
            return self._send(200, self._handle(text))
        d = self._body("json")
        if path == "/api/ask":
            return self._send(200, self._handle(str(d["text"]).strip()[:500]))
        if path == "/api/notes/done":
            a.store.set_done(int(d["id"]), bool(d.get("done", True)))
            return self._send(200, {"ok": True})
        if path == "/api/notes/delete":
            a.store.delete_note(int(d["id"]))
            return self._send(200, {"ok": True})
        if path == "/api/settings":
            a.settings.update(d)
            return self._send(200, a.settings.dict())
        if path == "/api/forget":
            if d.get("all"):
                n = a.store.forget()
            else:
                n = a.forget_recent(float(d.get("minutes", 5)))
            return self._send(200, {"deleted": n})
        if path == "/api/forget/frame":
            f = a.store.frame(int(d["id"]))
            n = a.store.forget(since=f["t"], before=f["t"] + 0.001) if f else 0
            return self._send(200, {"deleted": n})
        self._send(404, {"error": "not found"})

    def _handle(self, text):
        intent, kind, body = voice.route(text)
        if intent == "note" and body:
            return {"text": text, "intent": "note", "note": self.app.keep(body, kind)}
        return {"text": text, "intent": "ask", **ask.ask(self.app.store, body or text)}


def run(app, port, host="127.0.0.1"):
    Handler.app, Handler.port = app, port
    if not app.public:
        threading.Thread(target=app.reminders, daemon=True, name="reminders").start()
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"Déjà is open at http://{host}:{port}", flush=True)
    srv.serve_forever()
