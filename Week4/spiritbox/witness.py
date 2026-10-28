"""Gemma as the witness. It can't hear the audio. Whisper's own numbers pick the suspects, the lines it doubted
itself; Gemma reads each suspect the way a person reading the transcript would: is it something said earlier, coming
back, or a phrase that ends a video? Lines Whisper heard clearly are left alone: asked about every line, Gemma
struck 84 real ones."""
import difflib
import json
import os
import time
import urllib.error
import urllib.request

from . import ghosts

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("SPIRITBOX_GEMMA", "gemma3:4b")
# Asked for a verdict straight out, Gemma 3 4B would write "this is a direct echo of the earlier line" and then answer
# "real". Two plain yes/no questions, with the verdict worked out here, keep its answer and its reason together.
SCHEMA = {"type": "object", "required": ["reason", "said_before", "video_phrase"], "properties": {
    "reason": {"type": "string"},
    "said_before": {"type": "boolean"},
    "video_phrase": {"type": "boolean"}}}

PROMPT = """You are checking a meeting transcript made by Whisper, a speech-to-text model. During silence or noise
Whisper sometimes writes words nobody said: it repeats something from earlier in the meeting, or writes a phrase
that ends a video. Whisper doubted the line marked >>.

Transcript around the line:
{context}

The line to judge (marked >>):
{line}

Earlier in the meeting: {echo}

Answer two questions about the >> line:
said_before: does it repeat, or say again in other words, something already said earlier in this meeting?
video_phrase: is it the kind of phrase that ends a video or talk: thanking the audience, a goodbye, a captions credit?
Give a one-sentence reason first."""


def _sure(s):
    """Whisper's numbers in words; a small model reads words better than probabilities."""
    ns, lp = s.get("no_speech", 0), s.get("logprob", 0)
    hear = "Whisper thought this was probably silence" if ns > 0.6 else \
        "Whisper was unsure there was speech" if ns > 0.3 else "Whisper heard speech"
    conf = "and was confident in the words" if lp > -0.5 else "and was unsure of the words" if lp > -1 else \
        "and was guessing at the words"
    loop = ", the text repeats itself" if s.get("compression", 0) > 2.4 else ""
    return f"{hear} {conf}{loop}"


def _fmt(s, mark=False, prev=None):
    gap = f"after {s['start'] - (prev['end'] if prev else 0):.0f} s with nothing written, "
    lang = f", detected language {s['lang']}" if s.get("lang") not in (None, "en") else ""
    return f"{'>> ' if mark else '   '}at {s['start']:.0f}s, {gap}{s['text']!r} ({_sure(s)}{lang})"


def ask(prompt, model=MODEL):
    body = {"model": model, "stream": False, "format": SCHEMA, "messages": [{"role": "user", "content": prompt}],
            # file-backed weights: this laptop has no page file, so the model must not count against commit memory
            "options": {"temperature": 0, "use_mmap": True, "num_ctx": 2048}, "keep_alive": "10m"}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):  # now and then the reply comes back empty, or the model fails to load for lack of memory
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                text = json.loads(r.read())["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:  # 404: the model isn't pulled; waiting won't help
                raise
            time.sleep(30)
            continue
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(30)
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return {"reason": "the witness gave no answer", "kind": None, "verdict": "unsure"}


def suspect(s):
    """Whisper unsure there was speech and unsure of the words: the same cut-offs _sure() puts into words."""
    return s.get("no_speech", 0) > 0.3 and s.get("logprob", 0) < -0.5


def judge(segs, i, model=MODEL, window=3):
    line = lambda k, mark=False: _fmt(segs[k], mark, segs[k - 1] if k else None)  # noqa: E731
    ctx = "\n".join(line(k, k == i) for k in range(max(0, i - window), min(len(segs), i + window + 1)))
    # Whisper's ghosts are often echoes of something said minutes earlier, outside the window
    t = segs[i]["text"].lower()
    sim = [(difflib.SequenceMatcher(None, t, s["text"].lower()).ratio(), k) for k, s in enumerate(segs[:i])]
    best = max(sim, default=(0, None))
    echo = f"it closely matches the line at {segs[best[1]]['start']:.0f}s: {segs[best[1]]['text']!r}" \
        if best[0] >= 0.5 else "no earlier line looks like this one"
    out = ask(PROMPT.format(context=ctx, line=line(i, True), echo=echo), model)
    if "said_before" not in out:
        return out  # no answer: ask() already marked it unsure
    kind = "echo" if out["said_before"] else "sign-off" if out["video_phrase"] else None
    return {"verdict": "ghost" if kind else "real", "kind": kind, "reason": out["reason"]}


CLEAR = {"verdict": "real", "kind": None, "reason": "Whisper heard speech here and was sure of the words"}


def flag(segs, model=MODEL, language="en"):
    """Each segment with a verdict, kind and reason. The rules go first (they catch the stock phrases Whisper writes
    without doubting itself); Gemma reads the remaining suspects. On unseen meetings the two together beat either."""
    out = []
    for i, s in enumerate(ghosts.flag(segs, language)):
        if s["verdict"] == "ghost":
            out.append(dict(s, reason="a rule matched"))
        else:
            out.append(dict(s, **(judge(segs, i, model) if suspect(s) else CLEAR)))
    return out
