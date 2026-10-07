import argparse
import hashlib
import sys
from pathlib import Path

from . import ledger as L


def _print(res, entry=None):
    v = entry["body"]["verdict"] if entry else res["verdict"]
    print(f"{v}  score {res['score']}/100  life {res['life']:.2f}  noise {res['noise']:.2f}  ({res['seconds']}s)")
    for s in res["species"][:5]:
        print(f"  heard {s['name']}  logit {s['logit']}")
    if entry and entry["body"]["replay_of"]:
        print(f"  replay of {entry['body']['replay_of'][:12]} ({entry['body']['replay_votes']} matching landmarks)")
    if entry:
        print(f"  receipt {entry['hash'][:16]}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="trailear")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("listen", help="score a recording and seal a receipt")
    a.add_argument("audio")
    a.add_argument("--ledger", default="trailear.ledger.jsonl")
    a.add_argument("--note", default="")
    a.add_argument("--dry", action="store_true", help="score only, don't seal")
    v = sub.add_parser("verify", help="check a ledger offline (no model needed)")
    v.add_argument("ledger")
    v.add_argument("--anchor", help="head hash you published earlier; fails if the chain no longer reaches it")
    n = sub.add_parser("anchor", help="print the head hash to publish somewhere you can't edit")
    n.add_argument("ledger")
    s = sub.add_parser("serve", help="local web UI")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--ledger", default="trailear.ledger.jsonl")
    args = ap.parse_args(argv)

    if args.cmd == "verify":
        ok, msg = L.verify(args.ledger, args.anchor)
        print(("OK  " if ok else "FAIL  ") + msg)
        return 0 if ok else 1
    if args.cmd == "anchor":
        ok, msg = L.verify(args.ledger)
        if not ok:
            print("FAIL  " + msg)
            return 1
        print(L.Ledger(args.ledger).head)
        return 0
    if args.cmd == "serve":
        from .server import run
        return run(args.port, args.ledger)

    from .audio import load
    from .engine import Listener

    x = load(args.audio)
    res = Listener().listen(x)
    if args.dry:
        _print(res)
        return 0
    sha = hashlib.sha256(Path(args.audio).read_bytes()).hexdigest()
    _print(res, L.Ledger(args.ledger).seal(res, sha, args.note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
