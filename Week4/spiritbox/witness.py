"""Gemma as the witness. It can't hear the audio, so it judges each line the way a person reading a transcript would:
does this sound like something said in this conversation, given the lines around it, when it was said, and how
unsure Whisper was."""
import json
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("SPIRITBOX_GEMMA", "gemma3:4b")
KINDS = ["sign-off", "captions credit", "sound tag", "repetition loop", "wrong language", "invented line", "other"]

SCHEMA = {"type": "object", "required": ["verdict", "kind", "reason"], "properties": {
    "verdict": {"type": "string", "enum": ["real", "ghost", "unsure"]},
    "kind": {"type": ["string", "null"], "enum": KINDS + [None]},
    "reason": {"type": "string"}}}

PROMPT = """You are checking a speech-to-text transcript for hallucinations. Whisper sometimes writes words during
silence or noise: YouTube sign-offs ("Thanks for watching"), caption credits, sound tags like (music), a phrase
repeated over and over, text in the wrong language, or a plausible sentence nobody said. Nobody can hear the audio;
judge from the text, the timing, and Whisper's own confidence numbers.

no_speech is Whisper's probability that the window had no speech (high = probably silence). logprob is its average
log-probability for the words (closer to 0 = more confident). compression above 2.4 means the text repeats itself.

Transcript around the line, with start-end seconds:
{context}

The line to judge (marked >>):
{line}

Is the >> line real speech or a ghost? Answer as JSON with verdict, kind (null if real) and a one-sentence reason."""


def _fmt(s, mark=False):
    return (f"{'>> ' if mark else '   '}[{s['start']:.1f}-{s['end']:.1f}] {s['text']!r} "
            f"(no_speech {s.get('no_speech', 0):.2f}, logprob {s.get('logprob', 0):.2f}, "
            f"compression {s.get('compression', 0):.2f}, lang {s.get('lang', '?')})")


def ask(prompt, model=MODEL):
    body = {"model": model, "stream": False, "format": SCHEMA, "messages": [{"role": "user", "content": prompt}],
            # file-backed weights: this laptop has no page file, so the model must not count against commit memory
            "options": {"temperature": 0, "use_mmap": True, "num_ctx": 2048}, "keep_alive": "10m"}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


def judge(segs, i, model=MODEL, window=3):
    ctx = "\n".join(_fmt(s, k == i) for k, s in enumerate(segs) if abs(k - i) <= window)
    out = ask(PROMPT.format(context=ctx, line=_fmt(segs[i], True)), model)
    if out.get("verdict") == "real":
        out["kind"] = None
    return out


def flag(segs, model=MODEL):
    """Each segment with the witness's verdict, kind and reason."""
    return [dict(s, **judge(segs, i, model)) for i, s in enumerate(segs)]
