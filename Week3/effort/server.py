"""The local web app. Listens on 127.0.0.1 only and refuses requests from other sites
(wrong Host header or a cross-site fetch): what it receives is photos of your room.
Photos live in memory for the current run and are never written to disk.
"""
import json
import mimetypes
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import gemma, judge, learn, log, plan, see

WEB = Path(__file__).parent / "web"
MAX_BODY = 15 * 2**20


class App:
    def __init__(self, log_path=None, look=None, verdict=None):
        self.runs, self.lock = {}, threading.Lock()
        self.log_path = log_path
        self.look = look or see.look
        self.verdict = verdict or judge.verdict

    def factors(self):
        return learn.factors(log.done_moves(self.log_path))

    def add(self, kind, **f):
        return log.add(kind, path=self.log_path, **f)

    def see(self, data, on_items=None):
        photo = gemma.clean(data)
        t = time.perf_counter()
        items = self.look(photo, on_items)
        secs = round(time.perf_counter() - t, 1)
        run = uuid.uuid4().hex[:10]
        with self.lock:
            self.runs[run] = {"photo": photo, "items": items}
        self.add("see", run=run, photo=log.photo_id(photo), items=items, seconds=secs, model=gemma.MODEL)
        return {"run": run, "items": items, "seconds": secs}

    def plan(self, run, budget, removed=()):
        r = self.runs[run]
        removed = {int(i) for i in removed}
        f = self.factors()
        items = learn.apply([i for i in r["items"] if i["id"] not in removed], f)
        out = plan.make(items, int(budget))
        quick = plan.greedy(items, int(budget))
        r.update(costed={i["id"]: i for i in items}, budget=int(budget))
        self.add("plan", run=run, budget=int(budget), removed=sorted(removed), factors=f,
                 moves=[m["id"] for m in out["moves"]], score=out["score"],
                 greedy=[m["id"] for m in quick], greedy_score=round(plan.score(quick), 3))
        return {**out, "factors": f}

    def done(self, run, item_id, actual):
        it = self.runs[run]["costed"][int(item_id)]
        self.add("done", run=run, item=it["id"], what=it["what"], move_to=it["move_to"],
                 est_seconds=it["est_seconds"], cost=it["cost"], actual_seconds=round(float(actual), 1))
        return {"ok": True}

    def after(self, run, data):
        r = self.runs[run]
        photo = gemma.clean(data)
        t = time.perf_counter()
        v = self.verdict(r["photo"], photo, r["items"])
        v["seconds"] = round(time.perf_counter() - t, 1)
        self.add("after", run=run, photo=log.photo_id(photo), **{k: v[k] for k in v if k != "after_items"})
        return v


class Handler(BaseHTTPRequestHandler):
    app: App = None
    port = 0
    streaming = False

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if self.streaming:  # status already went out; the error becomes the last line
            return self._line(body)
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _line(self, obj):
        """One line of an NDJSON reply; the first call sends the headers. HTTP/1.0, so closing ends it."""
        if not self.streaming:
            self.streaming = True
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
        self.wfile.write(json.dumps(obj).encode() + b"\n")
        self.wfile.flush()

    def _trusted(self):
        # DNS rebinding: some other site's name pointed at 127.0.0.1
        if self.headers.get("Host", "") not in (f"127.0.0.1:{self.port}", f"localhost:{self.port}"):
            return False
        return self.headers.get("Sec-Fetch-Site", "same-origin") in ("same-origin", "none")

    def _body(self, kind):
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip()
        if kind == "json" and ctype != "application/json":
            raise ValueError("send application/json")
        if kind == "image" and not ctype.startswith("image/"):
            raise ValueError("send an image")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("photo too large (15 MB max)")
        raw = self.rfile.read(n)
        return json.loads(raw or b"{}") if kind == "json" else raw

    def do_GET(self):
        if not self._trusted():
            return self._send(403, {"error": "forbidden"})
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/factors":
            return self._send(200, {"factors": self.app.factors(), "moves": len(log.done_moves(self.app.log_path))})
        name = "index.html" if path == "/" else path.lstrip("/")
        f = (WEB / name).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return self._send(404, {"error": "not found"})
        self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")

    def do_POST(self):
        if not self._trusted():
            return self._send(403, {"error": "forbidden"})
        url = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        try:
            if url.path == "/api/see":  # streams each item as Gemma writes it, then the whole answer
                shown = []

                def on_items(items):
                    for it in items[len(shown):]:
                        shown.append(it)
                        self._line({"item": it})
                return self._line(self.app.see(self._body("image"), on_items))
            elif url.path == "/api/plan":
                b = self._body("json")
                out = self.app.plan(b["run"], b["budget"], b.get("removed", []))
            elif url.path == "/api/done":
                b = self._body("json")
                out = self.app.done(b["run"], b["item"], b["actual_seconds"])
            elif url.path == "/api/after":
                out = self.app.after(q["run"], self._body("image"))
            else:
                return self._send(404, {"error": "not found"})
            self._send(200, out)
        except KeyError:
            self._send(400, {"error": "unknown run or item; start again with a new photo"})
        except (ValueError, TypeError) as e:
            self._send(400, {"error": str(e)})
        except OSError as e:  # Ollama not running or timed out
            self._send(502, {"error": f"couldn't reach Gemma through Ollama ({e}). Is `ollama serve` running?"})


def run(app, port, host="127.0.0.1"):
    Handler.app, Handler.port = app, port
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"Effort Budget is open at http://{host}:{port}", flush=True)
    srv.serve_forever()
