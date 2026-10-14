import argparse
import json
import os
import sys

from . import ledger as L


def main(argv=None):
    ap = argparse.ArgumentParser(prog="thud", description="Find hollow tiles by listening to coin taps.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the web app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8766)))
    s.add_argument("--ledger", default="thud.ledger.jsonl")
    s.add_argument("--cert", help="TLS cert, so a phone on the LAN may use its mic")
    s.add_argument("--key")
    t = sub.add_parser("taps", help="print the taps found in an audio file")
    t.add_argument("audio")
    v = sub.add_parser("verify", help="check a ledger offline")
    v.add_argument("ledger")
    v.add_argument("--anchor")
    a = ap.parse_args(argv)

    if a.cmd == "serve":
        from .server import run
        return run(a.host, a.port, a.ledger, a.cert, a.key)
    if a.cmd == "taps":
        from .audio import load
        from .taps import extract
        print(json.dumps(extract(load(a.audio)), indent=1))
        return 0
    ok, msg = L.verify(a.ledger, a.anchor)
    print(("OK " if ok else "FAIL ") + msg)
    return 0 if ok else 1


sys.exit(main())
