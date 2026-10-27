"""Whisper, two ways: as everyone uses it, and with its guards off so it says what it "hears" in noise."""
import gc
import os
import threading
import time

MODEL = os.environ.get("SPIRITBOX_WHISPER", "base")

# Whisper skips a window when it's probably silence (no-speech probability over 0.6 and a low average log-probability),
# retries when the text repeats itself (compression ratio over 2.4), and can drop non-speech up front with a VAD.
# A spirit box is a radio with the squelch off; this is Whisper with all of that off.
GUARDS_OFF = dict(vad_filter=False, no_speech_threshold=None, log_prob_threshold=None,
                  compression_ratio_threshold=None, condition_on_previous_text=False, temperature=0)
DEFAULTS = {}  # faster-whisper's own defaults, the way a transcript of a meeting gets made

_models, _lock = {}, threading.Lock()


def model(size=MODEL):
    with _lock:
        if size not in _models:
            from faster_whisper import WhisperModel
            _models.clear()  # one at a time: this laptop has little commit memory to spare
            _models[size] = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=4)  # each thread holds its own MKL buffers
        return _models[size]


def transcribe(audio, guards=True, size=MODEL, language=None):
    """Segments with Whisper's own numbers about each one."""
    segs, info = model(size).transcribe(audio, beam_size=5 if guards else 1, language=language,
                                        **(DEFAULTS if guards else GUARDS_OFF))
    return [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(), "lang": info.language,
             "no_speech": round(s.no_speech_prob, 3), "logprob": round(s.avg_logprob, 3),
             "compression": round(s.compression_ratio, 2)} for s in segs if s.text.strip()]


def summon(audio, size=MODEL):
    """What Whisper hears in this audio when nothing tells it to stay quiet."""
    return transcribe(audio, guards=False, size=size)


def retry(fn, *args, tries=6, **kw):
    """Run again after a pause when the allocator fails; on a laptop with no page file free memory comes and goes."""
    for k in range(tries):
        try:
            return fn(*args, **kw)
        except (MemoryError, RuntimeError) as e:
            if k == tries - 1 or not isinstance(e, MemoryError) and "alloc" not in str(e):
                raise
            gc.collect()
            time.sleep(5 * (k + 1))
