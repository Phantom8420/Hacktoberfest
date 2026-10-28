"""python -m spiritbox summon white            # what Whisper hears in 30 s of white noise, guards off
python -m spiritbox summon room.wav --size tiny
python -m spiritbox exorcise meeting.mp3      # transcribe normally, then flag the lines that look like ghosts
                         [--judge rules|gemma] [--json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

from . import ghosts, listen, noise

LOG = Path("contacts.jsonl")


def source(what, seconds, seed):
    return noise.make(what, seconds, seed) if what in noise.KINDS else noise.load(what)


def summon(a):
    segs = listen.retry(listen.summon, source(a.what, a.seconds, a.seed), size=a.size)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": a.what, "seed": a.seed, "model": a.size, "lines": segs}
    with LOG.open("a", encoding="utf8") as f:
        f.write(json.dumps(rec) + "\n")
    if not segs:
        print("Nothing. The box stayed quiet.")
    for s in segs:
        print(f"[{s['start']:6.1f}s] {s['text']}  ({s['lang']}, no_speech {s['no_speech']:.2f})")


def exorcise(a):
    segs = listen.retry(listen.transcribe, noise.load(a.what), guards=True, size=a.size, language=a.language)
    if a.judge == "gemma":
        from . import witness
        out = witness.flag(segs, language=a.language)
    else:
        out = ghosts.flag(segs, a.language)
    if a.json:
        return print(json.dumps(out, indent=1))
    for s in out:
        mark = "GHOST" if s["verdict"] == "ghost" else "  ?  " if s["verdict"] == "unsure" else "     "
        why = f"  <- {s['kind']}" + (f": {s['reason']}" if s.get("reason") else "") if s["verdict"] != "real" else ""
        print(f"{mark} [{s['start']:6.1f}s] {s['text']}{why}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="spiritbox")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summon", help="listen to noise with Whisper's guards off")
    s.add_argument("what", help=f"a noise ({', '.join(noise.KINDS)}) or an audio file")
    s.add_argument("--seconds", type=float, default=30)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(fn=summon)
    e = sub.add_parser("exorcise", help="flag hallucinated lines in a normal transcript")
    e.add_argument("what", help="an audio or video file")
    e.add_argument("--judge", choices=["rules", "gemma"], default="gemma",
                   help="gemma: the rules first, then Gemma reads the lines Whisper doubted")
    e.add_argument("--language", default="en")
    e.add_argument("--json", action="store_true")
    e.set_defaults(fn=exorcise)
    for x in (s, e):
        x.add_argument("--size", default=listen.MODEL, help="whisper model: tiny, base, small...")
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
