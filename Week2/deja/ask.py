"""Answer a question from your own screen history.

Code does the finding (keywords + time window + full-text search) and the page always
shows the matching screenshots, so you can see the evidence. Gemma, local through
Ollama, only reads those few snippets and says which one answers you.
"""
import json
import os
import re
import time
import urllib.request

from . import when

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("DEJA_GEMMA", "gemma3:1b")

STOP = set("""a about after again all am an and any are as at be been before being but by can could did do does
doing find for from get got had has have how i i'd i'm if in into is it it's its just let like look looked
looking me my of on one or please remember saw say see seen show some something tell that the then there these
thing this those to up us was we were what what's when where which while who why will with you your deja
yesterday today tonight earlier ago last week morning afternoon evening night open opened""".split())

PROMPT = """You help someone find something they saw on their own screen. Below are numbered screens: the
time, the app, and the text read from each one. Answer the question in one or two short sentences using only
those screens, speaking to them as "you", and cite the screen you used like [2]. If no screen answers it, say
"I couldn't find that." Start with the answer itself. Never invent details that are not on the screens."""


def terms(question):
    words = re.findall(r"[a-z0-9][a-z0-9'+#.-]*", question.lower())
    return [w.strip(".'") for w in words if w.strip(".'") not in STOP and (len(w) > 1 or w.isdigit())]


def snippet(text, words, n=8):
    lines = [l for l in (text or "").splitlines() if l.strip()]
    hits = [l for l in lines if any(w in l.lower() for w in words)]
    return "\n".join((hits or lines)[:n])[:700]


def _gemma(question, hits, words, timeout):
    blocks = [f"[{i}] {time.strftime('%a %d %b %H:%M', time.localtime(h['t']))}, {h['app']}, "
              f"\"{h['title']}\"\n{snippet(h['text'], words)}" for i, h in enumerate(hits, 1)]
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps({
        "model": MODEL, "stream": False, "keep_alive": "10m", "options": {"temperature": 0.1},
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user", "content": "\n\n".join(blocks) + f"\n\nQuestion: {question}"}]}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"].strip()


def grounded(answer, hits):
    """Every number in the answer must appear on one of the screens it read."""
    seen = " ".join(f"{h['title']} {h['text']}" for h in hits)
    return all(n in seen for n in re.findall(r"\d+(?:[.,:]\d+)*", answer))


def ask(store, question, use_model=True, timeout=120, now=None):
    start, end, rest = when.past(question, now)
    words = terms(rest)
    hits = store.search(words, start and start.timestamp(), end and end.timestamp(), limit=8)
    out = {"question": question, "terms": words,
           "window": [start.timestamp(), end.timestamp()] if start else None,
           "hits": [{**h, "snippet": snippet(h["text"], words, 4)} for h in hits],
           "notes": store.search_notes(words), "answer": None, "cited": None, "model": None}
    for h in out["hits"]:
        h.pop("text", None)
    if use_model and hits and words:
        try:
            answer = _gemma(question, hits[:5], words, timeout)
        except Exception:
            return out  # Ollama not running: the screenshots still answer it
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= min(5, len(hits))]
        answer = re.sub(r"\s*\[(\d+)\]", "", answer).strip()
        if not grounded(answer, hits[:5]):
            return out  # a number that was never on screen: show the evidence, not the guess
        out["answer"] = answer
        out["cited"] = hits[cited[0] - 1]["id"] if cited else None
        out["model"] = MODEL
    return out


def gemma_ready():
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=2) as r:
            return any(m["name"] == MODEL for m in json.loads(r.read())["models"])
    except Exception:
        return False
