"""Local web UI. Audio never leaves the machine: the browser decodes to
32 kHz mono float32 and POSTs the raw samples here.
"""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from . import ledger as L
from .audio import SR
from .engine import Listener

WEB = Path(__file__).parent / "web"
MAX_BYTES = 125 * SR * 4


def run(port, ledger_path):
    lis = Listener()
    led = L.Ledger(ledger_path)

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/ledger":
                ok, msg = L.verify(led.path) if led.path.exists() else (True, "empty")
                slim = [{"hash": e["hash"], **{k: e["body"][k] for k in ("t", "verdict", "score", "seconds", "note")}}
                        for e in led.entries]
                return self._send(200, {"ok": ok, "msg": msg, "head": led.head, "entries": slim})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/listen":
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length", 0))
            if n < 4 * SR or n > MAX_BYTES or n % 4:
                return self._send(400, {"error": "need 1-125 s of float32 audio at 32 kHz"})
            raw = self.rfile.read(n)
            x = np.frombuffer(raw, dtype="<f4").copy()
            res = lis.listen(x)
            sha = hashlib.sha256(raw).hexdigest()
            entry = led.seal(res, sha, self.headers.get("X-Note", "")[:200])
            res.pop("phases"), res.pop("landmarks")
            self._send(200, {"result": res, "receipt": {"hash": entry["hash"], "prev": entry["prev"],
                                                        "body": {k: v for k, v in entry["body"].items() if k != "landmarks"}}})

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"trailear on http://127.0.0.1:{port}  ledger {led.path}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
