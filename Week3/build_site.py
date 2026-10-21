"""Build the static demo site in site/ (deploy that folder to Vercel or any static host).

    ollama pull gemma3:4b   # and keep Ollama running
    sh eval/fetch_photos.sh
    python build_site.py

Gemma looks at each sample room once, here; the page replays what it saw and does the planning
itself (effort/web/static.js).
"""
import json
import shutil
import sys
import time
from pathlib import Path

from effort import gemma, see

HERE = Path(__file__).parent
OUT = HERE / "site"
PHOTOS = HERE / "photos" / "raw" / "commons"
SAMPLES = [  # local name, title, author, license, source
    ("messy_uva_dorm", "Dorm room", "Packer1028", "CC0", "https://commons.wikimedia.org/wiki/File:Messy_UVA_dorm.jpg"),
    ("messy_office_room", "Home office", "OboeBlanket", "CC0", "https://commons.wikimedia.org/wiki/File:Messy_office_(room).jpg"),
    ("my_messy_room_16200326361", "Bedroom", "Adnan Islam", "CC BY 2.0",
     "https://commons.wikimedia.org/wiki/File:My_messy_room_(16200326361).jpg"),
]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(HERE / "effort" / "web", OUT)
    (OUT / "samples").mkdir()
    page = OUT / "index.html"
    page.write_text(page.read_text(encoding="utf8").replace(
        '<script src="app.js">', '<script src="static.js"></script>\n<script src="app.js">'), encoding="utf8")
    samples = []
    for name, title, author, lic, url in SAMPLES:
        photo = gemma.clean((PHOTOS / f"{name}.jpg").read_bytes())
        (OUT / "samples" / f"{name}.jpg").write_bytes(photo)
        t = time.perf_counter()
        items = see.look(photo)
        secs = round(time.perf_counter() - t, 1)
        print(f"{title}: {len(items)} items in {secs}s")
        samples.append({"file": f"{name}.jpg", "title": title, "author": author, "license": lic, "url": url,
                        "items": items, "seconds": secs})
    (OUT / "data.json").write_text(json.dumps({"model": gemma.MODEL, "samples": samples}, indent=1))
    print("built", OUT)


if __name__ == "__main__":
    if not (PHOTOS / f"{SAMPLES[0][0]}.jpg").exists():
        sys.exit("Fetch the sample photos first: sh eval/fetch_photos.sh")
    main()
