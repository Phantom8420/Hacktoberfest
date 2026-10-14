"""Hash-chained inspection receipts (Week 1's ledger, minus the audio fingerprint).
Tamper-evident, not tamper-proof: publish the head hash somewhere you can't
edit (a message to the landlord, a commit) and `verify --anchor` catches a rewrite.
"""
import hashlib
import json
import threading
import time
from pathlib import Path

GENESIS = "0" * 64


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Ledger:
    def __init__(self, path="thud.ledger.jsonl"):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.entries = [json.loads(l) for l in self.path.read_text("utf8").splitlines() if l.strip()] \
            if self.path.exists() else []

    @property
    def head(self):
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def seal(self, body, now=None):
        body = {"t": int(now if now is not None else time.time()), **body}
        with self._lock:  # two reports sealing at once would fork the chain
            entry = {"prev": self.head, "body": body}
            entry["hash"] = _h(entry)
            with open(self.path, "a", encoding="utf8") as f:
                f.write(json.dumps(entry) + "\n")
            self.entries.append(entry)
        return entry


def verify(path, anchor=None):
    """Returns (ok, message). With anchor, that hash must still be in the chain."""
    prev = GENESIS
    lines = [l for l in Path(path).read_text("utf8").splitlines() if l.strip()]
    for n, line in enumerate(lines, 1):
        e = json.loads(line)
        if e["prev"] != prev:
            return False, f"entry {n}: chain broken (prev hash mismatch)"
        if _h({"prev": e["prev"], "body": e["body"]}) != e["hash"]:
            return False, f"entry {n}: edited after sealing"
        prev = e["hash"]
        if anchor and prev.startswith(anchor):
            anchor = None
    if anchor:
        return False, "anchor not found: the chain was rewritten (or the anchor is wrong)"
    return True, f"{len(lines)} receipts intact, head {prev[:16]}"
