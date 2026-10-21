"""Phase 0 check: does Gemma see a photo at all, and how long does it take cold vs warm?

    python eval/smoke.py photos/raw/desk_1.jpg
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from effort import gemma  # noqa: E402

OUT = Path(__file__).parent / "results" / "smoke.json"


def unload():
    req = urllib.request.Request(f"{gemma.OLLAMA}/api/generate", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"model": gemma.MODEL, "keep_alive": 0}).encode())
    urllib.request.urlopen(req, timeout=60).read()


def main(path):
    raw = Path(path).read_bytes()
    img = gemma.clean(raw)
    unload()  # so the first call really is cold
    runs = []
    for label in ("cold", "warm", "warm"):
        t = time.perf_counter()
        reply = gemma.chat("List the objects you can see in this photo, comma separated.", [img])
        runs.append({"call": label, "seconds": round(time.perf_counter() - t, 1), "reply": reply[:300]})
        print(runs[-1])
    OUT.write_text(json.dumps({"model": gemma.MODEL, "photo_kb_sent": len(img) // 1024, "runs": runs}, indent=2))
    print("saved", OUT)


if __name__ == "__main__":
    main(sys.argv[1])
