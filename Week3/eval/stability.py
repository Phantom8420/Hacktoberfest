"""Does Gemma see the same room twice? And does it think two takes of one room differ?

For every photo, three "retakes" of the same unchanged scene: the photo itself, a slightly
shifted crop, and a slightly darker, slightly rotated copy. Real retakes from your own
phone (photos/raw/<zone>_1.jpg, _2, _3) are used as they are when present. Synthetic
retakes are a weaker test than real ones; the results file says which kind each one is.

For each scene it records:
  - the items found in each take, and how long each call took
  - overlap of item lists between takes (Jaccard; strict = same zone and similar name,
    loose = similar name anywhere, since Gemma names zones loosely)
  - the before/after judge on take 1 vs take 2, where the right answer is "same"

    python eval/stability.py              # all scenes, resumes where it stopped
    python eval/stability.py --limit 3
"""
import argparse
import difflib
import io
import json
import re
import sys
import time
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from effort import gemma, judge, plan, see  # noqa: E402

OUT = ROOT / "eval" / "results" / "stability.json"
RAW = ROOT / "photos" / "raw"


def jpeg(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def synthetic_takes(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    shifted = img.crop((int(w * .05), int(h * .03), int(w * .97), int(h * .98)))
    darker = ImageEnhance.Brightness(img).enhance(.88).rotate(2, resample=Image.BICUBIC, expand=False)
    return [gemma.clean(jpeg(x)) for x in (img, shifted, darker)]


def scenes():
    own = {}
    for p in sorted(RAW.glob("*_[123].jpg")):
        own.setdefault(re.sub(r"_[123]$", "", p.stem), []).append(p)
    for name, ps in own.items():
        if len(ps) == 3:
            yield name, "real", [gemma.clean(p.read_bytes()) for p in ps]
    for p in sorted((RAW / "commons").glob("*.jpg")):
        yield p.stem, "synthetic", synthetic_takes(p)


def match(a, b, strict):
    return (not strict or a["zone"] == b["zone"]) and difflib.SequenceMatcher(None, a["what"], b["what"]).ratio() >= .6


def jaccard(x, y, strict):
    if not x and not y:
        return 1.0
    hit = sum(any(match(a, b, strict) for b in y) for a in x)
    return hit / (len(x) + len(y) - hit)


def run_scene(name, kind, takes):
    looks = []
    for t in takes:
        t0 = time.perf_counter()
        items = see.look(t)
        looks.append({"seconds": round(time.perf_counter() - t0, 1), "items": items})
        print(f"  {name}: {len(items)} items in {looks[-1]['seconds']}s", flush=True)
    pairs = list(combinations(range(len(looks)), 2))
    t0 = time.perf_counter()
    same = judge.compare(takes[0], takes[1])
    return {"scene": name, "kind": kind, "looks": looks,
            "jaccard_strict": [round(jaccard(looks[i]["items"], looks[j]["items"], True), 3) for i, j in pairs],
            "jaccard_loose": [round(jaccard(looks[i]["items"], looks[j]["items"], False), 3) for i, j in pairs],
            "judge_same_scene": {k: same[k] for k in ("verdict", "margin", "raw")},
            "judge_seconds": round(time.perf_counter() - t0, 1)}


def summary(scenes):
    """Means over all scenes, with and without see.fixture(). The filter runs after Gemma answers,
    so applying it to the recorded lists is exactly what the app would have shown."""
    def keep(items):
        return [i for i in items if not see.fixture(i["what"], i["zone"], i["move_to"])]

    def mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    out = {"scenes": len(scenes), "judge_said_same": sum(s["judge_same_scene"]["verdict"] == "same" for s in scenes),
           "seconds_per_look": mean([l["seconds"] for s in scenes for l in s["looks"]])}
    for name, f in (("raw", lambda x: x), ("filtered", keep)):
        for strict in (False, True):
            js = [jaccard(f(s["looks"][i]["items"]), f(s["looks"][j]["items"]), strict)
                  for s in scenes for i, j in combinations(range(len(s["looks"])), 2)]
            out[f"{name}_{'strict' if strict else 'loose'}"] = mean(js)
        out[f"{name}_items_per_look"] = mean([len(f(l["items"])) for s in scenes for l in s["looks"]])
        # what the user actually sees: is the one move the same thing on every take?
        for budget in (30, 90, 300):
            same = []
            for s in scenes:
                first, *rest = [plan.make(f(l["items"]), budget)["one"] for l in s["looks"]]
                if first:
                    same.append(float(all(o and match(first, o, False) for o in rest)))
            out[f"{name}_same_one_move_{budget}s"] = mean(same)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    done = json.loads(OUT.read_text()) if OUT.exists() else {"model": gemma.MODEL, "scenes": []}
    have = {s["scene"] for s in done["scenes"]}
    for n, (name, kind, takes) in enumerate(scenes()):
        if a.limit is not None and n >= a.limit:
            break
        if name in have:
            continue
        print(name, kind, flush=True)
        done["scenes"].append(run_scene(name, kind, takes))
        OUT.write_text(json.dumps(done, indent=1))  # after every scene, so a crash loses one at most
    done["summary"] = summary(done["scenes"])
    OUT.write_text(json.dumps(done, indent=1))
    print(done["summary"])
    print("saved", OUT)


if __name__ == "__main__":
    main()
