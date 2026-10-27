"""Gemma as the witness. It can't hear the audio, so it judges each line the way a person reading a transcript would:
does this sound like something said in this conversation, given the lines around it, when it was said, and how
unsure Whisper was."""
import difflib
import json
import os
import time
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("SPIRITBOX_GEMMA", "gemma3:4b")
KINDS = ["sign-off", "captions credit", "sound tag", "repetition loop", "wrong language", "echo", "invented line",
         "other"]

# reason comes first so the model explains itself before it commits to a verdict
SCHEMA = {"type": "object", "required": ["reason", "kind", "verdict"], "properties": {
    "reason": {"type": "string"},
    "kind": {"type": "string", "enum": ["none"] + KINDS},
    "verdict": {"type": "string", "enum": ["real", "ghost", "unsure"]}}}

PROMPT = """You are checking a speech-to-text transcript for hallucinations. Whisper sometimes writes words during
silence or noise: YouTube sign-offs ("Thanks for watching"), caption credits, sound tags like (music), a phrase
repeated over and over, text in the wrong language, a plausible sentence nobody said, or an echo: an earlier line
written again, often reworded, during a long pause. Nobody can hear the audio; judge from the words, the timing and
how sure Whisper was. Most lines in a transcript are real: a normal sentence that fits the meeting, which Whisper
heard as speech, is real even after a pause. Call it a ghost only when something specific gives it away.

Transcript around the line:
{context}

The line to judge (marked >>):
{line}

Is the >> line real speech or a ghost? Give a one-sentence reason, then the kind of ghost it is ("none" if it is ordinary speech), then the verdict."""


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
        except (urllib.error.URLError, ConnectionError):
            if attempt == 2:
                raise
            time.sleep(30)
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return {"reason": "the witness gave no answer", "kind": "none", "verdict": "unsure"}


def judge(segs, i, model=MODEL, window=3):
    line = lambda k, mark=False: _fmt(segs[k], mark, segs[k - 1] if k else None)  # noqa: E731
    ctx = "\n".join(line(k, k == i) for k in range(max(0, i - window), min(len(segs), i + window + 1)))
    # Whisper's ghosts are often echoes of something said minutes earlier, outside the window
    t = segs[i]["text"].lower()
    sim = [(difflib.SequenceMatcher(None, t, s["text"].lower()).ratio(), k) for k, s in enumerate(segs[:max(0, i - window)])]
    if sim and max(sim)[0] >= 0.5:
        ctx = "Earlier, a similar line:\n" + line(max(sim)[1]) + "\n...\n" + ctx
    out = ask(PROMPT.format(context=ctx, line=line(i, True)), model)
    if out.get("verdict") == "real" or out.get("kind") == "none":
        out["kind"] = None
    return out


def flag(segs, model=MODEL):
    """Each segment with the witness's verdict, kind and reason."""
    return [dict(s, **judge(segs, i, model)) for i, s in enumerate(segs)]
