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

# a 1B model refuses too readily ("I couldn't find that" with the code right there), so the prompt leans the other
# way; grounded() and the quote fallback below catch what that lets through
PROMPT = """You help someone find something they saw on their own screen. Below are numbered screens: the
time, the app, and the text read from each one. The answer is usually written on one of them. Answer the question
in one short sentence, speaking to them as "you", quoting the exact name, number or code from the screen, and cite
the screen you used like [2]. Start with the answer itself. Never invent details that are not on the screens. Only
if none of the screens mentions it at all, say "I couldn't find that." """


def terms(question):
    words = re.findall(r"[a-z0-9][a-z0-9'+#.-]*", question.lower())
    return [w.strip(".'") for w in words if w.strip(".'") not in STOP and (len(w) > 1 or w.isdigit())]


def snippet(text, words, n=8):
    lines = [l for l in (text or "").splitlines() if l.strip()]
    near = {j for i, l in enumerate(lines) if any(w in l.lower() for w in words) for j in range(i - 2, i + 3)}
    keep = [l for i, l in enumerate(lines) if i in near]  # "Lemon cake" alone would hide "180 C for 45 minutes"
    return "\n".join((keep or lines)[:n])[:700]


EXPAND = """List up to 8 words that would likely be printed on a screen that answers this question: synonyms,
related terms, brand or unit words. Lowercase, comma separated, nothing else."""


def _chat(system, user, timeout):
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps({
        "model": MODEL, "stream": False, "keep_alive": "10m", "options": {"temperature": 0.1},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"].strip()


def related(question, timeout=10):
    """Words the screen might use instead of yours ("cheap flight" -> fare, price): search by meaning,
    not only by the exact word, without storing anything but the hashed index."""
    try:
        reply = _chat(EXPAND, question, timeout)
    except Exception:
        return []
    if "," not in reply:  # not the list it was asked for ("Invalid syntax.")
        return []
    return [w for w in terms(reply.replace(",", " ")) if len(w) >= 3][:8]


def tidy(answer):
    """Small models pad: drop an "I understand you're asking..." opening or a chat line's
    "Lena: " speaker label copied from the screen; a refusal is no answer."""
    answer = re.sub(r"^(I understand|Okay|Sure|Based on the screens).*?[.:](\s+|$)", "", answer.strip(), flags=re.I)
    answer = re.sub(r"^[A-Z][a-z]+:\s+", "", answer).strip("\"“”")
    return None if not answer or re.match(r"(I|You) (couldn|could not|can.t|cannot|don.t)", answer) else answer


def quote(hits, words):
    """No model, or it gave up: the line on the top screens that best matches the question, with its screen id.
    Needs half the question's words between the line and its window title, so a lone common word is not enough."""
    need, best = (len(set(words)) + 1) // 2, None
    for h in hits[:3]:
        in_title = {w for w in words if w in (h["title"] or "").lower()}
        lines = [l.strip() for l in (h["text"] or "").splitlines() if l.strip()]
        for i, line in enumerate(lines):
            found = {w for w in words if w in line.lower()}
            if found and len(found | in_title) >= need and (not best or len(found) > best[0]):
                # a heading like "Lemon olive oil cake" holds no answer; the figures are on the lines below it
                best = (len(found), line if re.search(r"\d", line) else " / ".join(lines[i:i + 3]), h["id"])
    return best and best[1:]


def _gemma(question, hits, words, timeout):
    blocks = [f"[{i}] {time.strftime('%a %d %b %H:%M', time.localtime(h['t']))}, {h['app']}, "
              f"\"{h['title']}\"\n{snippet(h['text'], words)}" for i, h in enumerate(hits, 1)]
    return _chat(PROMPT, "\n\n".join(blocks) + f"\n\nQuestion: {question}", timeout)


def grounded(answer, hits):
    """Every number in the answer must appear on one of the screens it read."""
    seen = " ".join(f"{h['title']} {h['text']}" for h in hits)
    return all(n in seen for n in re.findall(r"\d+(?:[.,:]\d+)*", answer))


def ask(store, question, use_model=True, timeout=120, now=None):
    start, end, rest = when.past(question, now)
    words = terms(rest)
    span = (start and start.timestamp(), end and end.timestamp())
    hits = store.search(words, *span, limit=8)
    asked = words
    if use_model and words and len(hits) < 3:  # few exact matches: also look for what the screen may have said
        extra = [w for w in related(rest, min(timeout, 10)) if w not in words]
        if extra:
            seen = {h["id"] for h in hits}
            hits += [h for h in store.search(extra, *span, limit=8) if h["id"] not in seen][:8 - len(hits)]
            words = words + extra
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
            answer = ""  # Ollama not running
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= min(5, len(hits))]
        answer = tidy(re.sub(r"\s*\[(\d+)\]", "", answer))
        if answer and grounded(answer, hits[:5]):  # a number never on screen means a guess: drop it
            out.update(answer=answer, cited=hits[cited[0] - 1]["id"] if cited else None, model=MODEL)
            return out
    q = quote(hits, asked)
    if q:
        out["answer"], out["cited"] = f"On your screen: “{q[0]}”", q[1]
    return out


def gemma_ready():
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=2) as r:
            return any(m["name"] == MODEL for m in json.loads(r.read())["models"])
    except Exception:
        return False
