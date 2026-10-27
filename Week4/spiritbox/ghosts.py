"""The rules a careful engineer would write to catch Whisper's ghosts: a list of known phrases plus Whisper's own numbers.
This is the baseline the witness (Gemma) has to beat."""
import re

# Lines Whisper learned from the end of subtitled videos. It says them to an empty room.
PHRASES = ["thanks for watching", "thank you for watching", "subscribe", "like and subscribe", "see you next time",
           "see you in the next video", "subtitles by", "captions by", "transcribed by", "amara.org", "thank you.",
           "bye.", "you", "i'll see you", "please like", "next video"]


def norm(s):
    return re.sub(r"[^a-z0-9.' ]", "", s.lower()).strip()


def kind(seg, prev=None, language="en"):
    """Why this line looks like a ghost, or None if it looks like speech."""
    t, n = seg["text"].strip(), norm(seg["text"])
    if re.fullmatch(r"[\[(♪*].*[\])♪*]", t):
        return "sound tag"  # (water splashing), [MUSIC], ♪
    if n in PHRASES or any(p in n for p in PHRASES if len(p) > 8):
        return "sign-off"
    if seg.get("compression", 0) > 2.4 or prev and norm(prev["text"]) == n:
        return "repetition loop"
    if seg.get("lang") and language and seg["lang"] != language:
        return "wrong language"
    if seg.get("no_speech", 0) > 0.6 and seg.get("logprob", 0) < -1:
        return "unsure audio"  # Whisper itself thought this window was probably silence
    return None


def flag(segs, language="en"):
    """Each segment with verdict ('ghost' or 'real') and kind."""
    return [dict(s, verdict="ghost" if (k := kind(s, segs[i - 1] if i else None, language)) else "real", kind=k)
            for i, s in enumerate(segs)]
