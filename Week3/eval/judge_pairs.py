"""The before/after judge on real tidy-ups: photos/raw/pairs/<name>_before.jpg and _after.jpg.

Each pair is judged both ways round. before -> after should come out "tidier", and
after -> before (the room getting messy again) should come out "messier".
Your own pairs go in the same folder under the same names.

    python eval/judge_pairs.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from effort import gemma, judge, see  # noqa: E402

PAIRS = ROOT / "photos" / "raw" / "pairs"
OUT = ROOT / "eval" / "results" / "judge_pairs.json"


def main():
    out = []
    for b in sorted(PAIRS.glob("*_before.jpg")):
        name = b.stem.removesuffix("_before")
        before, after = (gemma.clean(p.read_bytes()) for p in (b, PAIRS / f"{name}_after.jpg"))
        t = time.perf_counter()
        items = see.look(before)
        fwd = judge.verdict(before, after, items)
        back = judge.verdict(after, before, fwd["after_items"])
        row = {"pair": name, "seconds": round(time.perf_counter() - t),
               "forward": {k: v for k, v in fwd.items() if k != "after_items"},
               "backward": {k: v for k, v in back.items() if k != "after_items"},
               "items_before": items, "items_after": fwd["after_items"]}
        print(name, "forward:", fwd["verdict"], fwd["mess_removed"], "| backward:", back["verdict"], flush=True)
        out.append(row)
    OUT.write_text(json.dumps(out, indent=1))
    print("saved", OUT)


if __name__ == "__main__":
    main()
