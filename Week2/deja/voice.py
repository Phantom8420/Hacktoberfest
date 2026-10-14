"""Speech to text with Whisper (open weights, runs on the CPU), and the rule that
decides whether you asked something or told it something to keep.
"""
import io
import os
import re
import threading

import numpy as np

MODEL = os.environ.get("DEJA_WHISPER", "base.en")
_model, _lock = None, threading.Lock()


def pcm(data):
    """Any audio the browser records (webm, ogg, wav) -> 16 kHz mono float32."""
    import av
    with av.open(io.BytesIO(data)) as c:
        rs = av.AudioResampler(format="flt", layout="mono", rate=16000)
        chunks = [f.to_ndarray().ravel() for fr in c.decode(audio=0) for f in rs.resample(fr)]
        chunks += [f.to_ndarray().ravel() for f in rs.resample(None)]
    return np.concatenate(chunks) if chunks else np.zeros(0, np.float32)


def transcribe(data):
    global _model
    audio = pcm(data)
    if len(audio) < 16000 * 0.3:
        return ""
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=4)
        segs, _ = _model.transcribe(audio, beam_size=1, vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip()


KEEP = re.compile(r"^(?:(?:hey |ok |okay )?deja[,.]? )?(remind me(?: to)?|remember(?: that| to)?|note(?: that|:)?|"
                  r"make a note(?: that)?|add|to ?do:?|don'?t (?:let me )?forget(?: to)?|i (?:need|have|want) to|"
                  r"save)\b[,:]?\s*", re.I)


def route(text):
    """('note', kind, body) for things to keep, ('ask', None, text) for questions."""
    m = KEEP.match(text.strip())
    if not m:
        return "ask", None, text.strip()
    verb = m.group(1).lower()
    kind = ("reminder" if verb.startswith("remind") else
            "todo" if verb.endswith(" to") or verb.startswith(("add", "to", "don", "i ")) else "note")
    body = text.strip()[m.end():].strip().rstrip(".")
    return "note", kind, body[:1].upper() + body[1:]
