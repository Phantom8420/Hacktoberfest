"""Local web app. Audio, photos and reports stay on this machine; only the
numeric tap features go to the TabPFN API, and only if local TabPFN can't load.
"""
import base64
import hashlib
import json
import ssl
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from . import ledger as L
from . import demo, report, score, taps

WEB = (Path(__file__).parent / "web").resolve()
MAX_AUDIO = 300 * taps.SR * 4
MAX_JSON = 40 * 1024 * 1024
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
         ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml",
         ".woff2": "font/woff2", ".mp4": "video/mp4"}


def gemma_ready():
    try:
        with urllib.request.urlopen(f"{report.OLLAMA}/api/tags", timeout=1.5) as r:
            return any(m["name"].startswith(report.MODEL) for m in json.loads(r.read())["models"])
    except Exception:
        return False


def run(host, port, ledger_path, cert=None, key=None):
    led = L.Ledger(ledger_path)

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def _json(self):
            # a JSON content type forces a CORS preflight, so other sites can't write receipts
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("send application/json")
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= MAX_JSON:
                raise ValueError("request body missing or too large")
            return json.loads(self.rfile.read(n))

        def do_GET(self):
            try:
                self._get()
            except Exception as e:
                self._send(500, {"error": f"server error: {e}"})

        def _get(self):
            path = self.path.split("?")[0]
            if path == "/api/status":
                return self._send(200, {"gemma": gemma_ready(), "gemma_model": report.MODEL,
                                        "tabpfn": score._backend or "not used yet", "head": led.head})
            if path == "/api/demo":
                # a made-up floor: about one tile in six hollow, returned as audio plus the truth
                rng = np.random.default_rng()
                n = 20
                truth = [bool(v) for v in rng.random(n) < 0.17]
                truth[rng.integers(n)] = True
                body = demo.floor(truth, seed=int(rng.integers(1 << 30))).astype("<f4").tobytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Truth", "".join("H" if t else "S" for t in truth))
                self.end_headers()
                return self.wfile.write(body)
            if path == "/api/ledger":
                ok, msg = L.verify(led.path) if led.path.exists() else (True, "no receipts yet")
                slim = [{"hash": e["hash"], "t": e["body"]["t"], "room": e["body"].get("room", ""),
                         "flagged": e["body"].get("flagged", 0), "tapped": e["body"].get("tapped", 0)}
                        for e in led.entries]
                return self._send(200, {"ok": ok, "msg": msg, "head": led.head, "entries": slim})
            f = (WEB / (path.lstrip("/") or "index.html")).resolve()
            if f.is_relative_to(WEB) and f.is_file() and f.suffix in TYPES:
                return self._send(200, f.read_bytes(), TYPES[f.suffix])
            self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                if self.path == "/api/taps":
                    n = int(self.headers.get("Content-Length", 0))
                    if n < taps.SR * 4 // 2 or n > MAX_AUDIO or n % 4:
                        return self._send(400, {"error": "send 0.5-300 s of mono float32 audio at 32 kHz"})
                    x = np.frombuffer(self.rfile.read(n), dtype="<f4")
                    return self._send(200, {"taps": taps.extract(x)})
                if self.path == "/api/score":
                    j = self._json()
                    rows, labels = j["rows"], j.get("labels") or [None] * len(j["rows"])
                    out = {"suspicion": score.suspicion(rows)}
                    try:
                        out["backend"], out["p_hollow"] = score.classify(rows, labels)
                    except (ValueError, RuntimeError) as e:
                        out["note"] = str(e)
                    return self._send(200, out)
                if self.path == "/api/report":
                    j = self._json()
                    insp, photos = j["inspection"], j.get("photos", [])[:6]
                    tiles = insp["tiles"]
                    body = {
                        "site": insp.get("site", "")[:120], "room": insp.get("room", "")[:120],
                        "rows": insp["rows"], "cols": insp["cols"],
                        "tapped": sum(1 for t in tiles if t.get("tapped")),
                        "flagged": sum(1 for t in tiles if (t.get("p_hollow") or 0) >= 0.5 or t.get("label") == "hollow"),
                        "tiles": [{k: t.get(k) for k in ("r", "c", "label", "p_hollow", "features")} for t in tiles],
                        "tabpfn": insp.get("backend"),
                        "photo_sha256": [hashlib.sha256(base64.b64decode(p)).hexdigest() for p in photos],
                    }
                    md, model = report.write(insp, photos)
                    entry = led.seal({**body, "writer": model,
                                      "report_sha256": hashlib.sha256(md.encode()).hexdigest()})
                    return self._send(200, {"report": md, "writer": model,
                                            "receipt": {"hash": entry["hash"], "prev": entry["prev"]}})
                self._send(404, {"error": "not found"})
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                self._send(400, {"error": f"bad request: {e}"})

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer((host, port), H)
    scheme = "http"
    if cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        scheme = "https"
    print(f"thud on {scheme}://{host}:{port}  ledger {led.path}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
