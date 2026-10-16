"""Build the static demo site in site/ (deploy that folder to Vercel or any static host).

    ollama pull gemma3:1b   # and keep Ollama running
    python build_site.py

The sample day from deja/demo.py is searched and answered by the real code and Gemma once, here;
the page replays those answers and does its own search in the browser for anything else.
"""
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from deja import ask, demo, when
from deja.store import Store

HERE = Path(__file__).parent
OUT = HERE / "site"
QUESTIONS = [
    "What was that hotel I looked at yesterday?",
    "What error did I get this morning?",
    "Which hotel had a sea view?",
    "What was my flight gate?",
    "What's my booking reference?",
    "When is the project kickoff?",
    "How long does the lemon cake bake?",
    "What was the discount code for the shoes?",
    "Where are the new logo files?",
    "When is the launch review?",
]


def main():
    if not ask.gemma_ready():
        sys.exit(f"Start Ollama with {ask.MODEL} first: the answers are written by it.")
    # a fixed early afternoon, so "this morning" and "yesterday" land on the right screens
    now = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = Store(Path(tmp))
        demo.seed(store, now.timestamp())
        answers = {}
        for q in QUESTIONS:
            # a 1B model sometimes gives up or pads; try the same keywords worded a little differently
            for asked in (q, q.lower().rstrip("?"), q.rstrip("?") + ", please?"):
                r = ask.ask(store, asked, now=now)
                if r["answer"]:
                    break
            else:
                r["answer"] = None  # the page shows the matching screens instead
            print(f"{q}\n  -> {r['answer']}")
            if r["answer"]:
                key = " ".join(sorted(ask.terms(when.past(q, now)[2])))
                answers[key] = {"answer": r["answer"], "cited": r["cited"], "hits": [h["id"] for h in r["hits"]]}
        t0 = now.timestamp()
        data = {
            "gemma_model": ask.MODEL, "mb": store.stats()["mb"], "answers": answers,
            "frames": [{"id": f["id"], "ago": t0 - f["t"], "app": f["app"], "title": f["title"],
                        "image": f["image"], "text": f["text"]} for f in store.timeline()
                       for f in [store.frame(f["id"])]],
            "notes": [{"id": n["id"], "text": n["text"], "kind": n["kind"], "done": n["done"],
                       "due_in": n["due"] and n["due"] - t0} for n in store.notes()],
        }
        shutil.rmtree(OUT, ignore_errors=True)
        for f in data["frames"]:  # the sample screens are public, so the site gets them decrypted
            (OUT / "frames" / f["image"]).parent.mkdir(parents=True, exist_ok=True)
            (OUT / "frames" / f["image"]).write_bytes(store.image(f["image"]))
        store.db.close()  # Windows will not delete an open database
    web = HERE / "deja" / "web"
    for name in ("app.css", "app.js", "static.js", "demo.gif"):
        shutil.copy(web / name, OUT / name)
    # the local app stays offline and falls back to Segoe UI; the hosted pages can fetch Inter
    font = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">\n</head>'
    html = (web / "app.html").read_text("utf8")
    html = html.replace("Ask it anything below, by typing or with the mic.", "Ask it anything below.")
    html = html.replace("</head>", font)
    html = html.replace('<script src="app.js"></script>', '<script src="static.js"></script>\n<script src="app.js"></script>')
    (OUT / "app.html").write_text(html, "utf8")
    get = ('<nav class="wnav"><a href="https://github.com/Phantom8420/Hacktoberfest/releases/download/deja-v0.1.0/'
           'Deja-windows.zip">Download</a>')
    for name in ("index.html", "how.html"):
        page = (web / name).read_text("utf8").replace("</head>", font).replace('<nav class="wnav">', get)
        (OUT / name).write_text(page, "utf8")
    (OUT / "data.json").write_text(json.dumps(data, indent=1), "utf8")
    print(f"{len(answers)}/{len(QUESTIONS)} answers kept, site written to {OUT}")


if __name__ == "__main__":
    main()
