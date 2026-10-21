"""runs.jsonl: one line per event. Photos are never stored, only a hash to tell runs apart."""
import hashlib
import json
import time
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "runs.jsonl"


def photo_id(data):
    return hashlib.sha256(data).hexdigest()[:16]


def add(kind, path=None, **fields):
    rec = {"t": round(time.time(), 1), "kind": kind, **fields}
    with open(path or PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def read(path=None):
    p = Path(path or PATH)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def done_moves(path=None):
    return [r for r in read(path) if r["kind"] == "done"]
