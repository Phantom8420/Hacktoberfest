"""Hash-chained receipts. Tamper-evident, not tamper-proof: anyone who can
rewrite the whole file can rebuild the chain, so post the head hash
somewhere you can't edit if you want it to mean something.
"""
import hashlib
import json
import time
from pathlib import Path

from . import fingerprint as fp

GENESIS = "0" * 64
MIN_VOTES = 8  # 34,168 cross-recording ESC-50 pairs peaked at 6 votes (eval/run_eval.py)


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Ledger:
    def __init__(self, path="trailear.ledger.jsonl"):
        self.path = Path(path)
        self.entries = [json.loads(l) for l in self.path.read_text("utf8").splitlines() if l.strip()] \
            if self.path.exists() else []

    @property
    def head(self):
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def find_replay(self, query_phases):
        best = None
        for e in self.entries:
            v, share = fp.best_match(fp.unpack(e["body"]["landmarks"]), query_phases)
            if v >= MIN_VOTES and (best is None or v > best[1]):
                best = (e, v, share)
        return best

    def seal(self, result, audio_sha256, note="", now=None):
        replay = self.find_replay(result["phases"])
        body = {
            "t": int(now if now is not None else time.time()),
            "audio_sha256": audio_sha256,
            "landmarks": fp.pack(result["landmarks"]),
            "seconds": result["seconds"],
            "score": result["score"],
            "verdict": result["verdict"],
            "nature_gap": result.get("nature_gap"),
            "life": result["life"],
            "noise": result["noise"],
            "species": result["species"],
            "note": note,
            "replay_of": replay[0]["hash"] if replay else None,
            "replay_votes": replay[1] if replay else None,
        }
        if replay:
            body["verdict"] = "REPLAY"
            body["score"] = 0
        entry = {"prev": self.head, "body": body}
        entry["hash"] = _h({"prev": entry["prev"], "body": body})
        self.entries.append(entry)
        with open(self.path, "a", encoding="utf8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry


def verify(path, anchor=None):
    """Offline check, no model needed. Returns (ok, message).
    With anchor, also require that hash to sit in the chain: a rewrite made after
    you published the anchor can't reproduce it."""
    prev = GENESIS
    lines = [l for l in Path(path).read_text("utf8").splitlines() if l.strip()]
    for n, line in enumerate(lines, 1):
        e = json.loads(line)
        if e["prev"] != prev:
            return False, f"entry {n}: chain broken (prev hash mismatch)"
        if _h({"prev": e["prev"], "body": e["body"]}) != e["hash"]:
            return False, f"entry {n}: body was edited after sealing"
        prev = e["hash"]
        if anchor and prev.startswith(anchor):
            anchor = None
    if anchor:
        return False, "anchor hash not found: chain was rewritten (or the anchor is wrong)"
    return True, f"{len(lines)} entries intact, head {prev[:16]}"
