"""Fetch a labeled subset of ESC-50 (Piczak 2015, CC BY-NC 4.0) for evaluation.

Usage: python eval/fetch_esc50.py OUT_DIR [PER_FOLD]
Writes wav files plus manifest.json. Not redistributed with this repo.

Groups were fixed before any clip was scored:
  life     -> expect TOUCHED_GRASS / GRASS_PLUS_NOISE
  ambient  -> rain, waves, wind...: must not be accused (HUMAN_MADE); grass is a bonus
  human    -> must not score as grass
Domestic animals (dog, cat, hen...) are left out because the labels call them ambiguous.
"""
import csv
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/karolpiczak/ESC-50/master/"
GROUPS = {
    "life": ["chirping_birds", "crow", "frog", "insects", "crickets"],
    "ambient": ["rain", "sea_waves", "wind", "thunderstorm", "water_drops", "pouring_water", "crackling_fire"],
    "human": ["engine", "car_horn", "siren", "train", "airplane", "helicopter", "chainsaw", "church_bells",
              "vacuum_cleaner", "clock_alarm", "keyboard_typing", "washing_machine", "hand_saw", "laughing",
              "clapping", "mouse_click"],
}
CLS = {c: g for g, cs in GROUPS.items() for c in cs}


def get(url):
    for wait in (0, 3, 10, 30):
        time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "trailear-eval/0.1"})
            return urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:
            err = e
    raise err


def main(out, per_fold=4):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(io.StringIO(get(RAW + "meta/esc50.csv").decode())))
    seen, manifest = {}, []
    for r in rows:
        if r["category"] not in CLS:
            continue
        key = (r["category"], r["fold"])
        if seen.get(key, 0) >= per_fold:
            continue
        seen[key] = seen.get(key, 0) + 1
        f = out / r["filename"]
        if not f.exists():
            f.write_bytes(get(RAW + "audio/" + r["filename"]))
        manifest.append({"file": r["filename"], "cls": CLS[r["category"]], "category": r["category"],
                         "fold": int(r["fold"]), "src": r["src_file"]})
    json.dump(manifest, open(out / "manifest.json", "w"), indent=1)
    print(len(manifest), "clips")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
