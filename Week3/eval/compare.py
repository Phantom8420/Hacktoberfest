"""Before/after pairs where the right answer is known: photos/raw/<name>_before.jpg and
<name>_after.jpg, the after one tidied by hand. The judge must say "tidier" both ways round.

    python eval/compare.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from effort import gemma, judge, see  # noqa: E402

OUT = ROOT / "eval" / "results" / "compare.json"
RAW = ROOT / "photos" / "raw"


def main():
    rows = []
    for b in sorted(RAW.glob("*_before.jpg")):
        a = b.with_name(b.name.replace("_before", "_after"))
        if not a.exists():
            continue
        before, after = gemma.clean(b.read_bytes()), gemma.clean(a.read_bytes())
        t0 = time.perf_counter()
        items = see.look(before)
        v = judge.verdict(before, after, items)
        rows.append({"pair": b.stem[:-7], "verdict": v["verdict"], "margin": v["margin"], "raw": v["raw"],
                     "items_before": v["items_before"], "items_after": v["items_after"],
                     "mess_removed": v["mess_removed"], "seconds": round(time.perf_counter() - t0, 1)})
        print(rows[-1]["pair"], rows[-1]["verdict"], flush=True)
    if not rows:
        print("no *_before.jpg / *_after.jpg pairs in", RAW)
        return
    OUT.write_text(json.dumps({"model": gemma.MODEL, "pairs": rows,
                               "correct": sum(r["verdict"] == "tidier" for r in rows)}, indent=1))
    print("saved", OUT)


if __name__ == "__main__":
    main()
