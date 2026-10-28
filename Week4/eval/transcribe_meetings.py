"""Transcribe eval/meetings/*.wav the normal way (Whisper's guards on) and label every line: real if it's something a
voice said, a ghost if it came out of a pause. Writes eval/transcripts.json.

    python eval/transcribe_meetings.py [whisper sizes...]     # default: tiny base small
"""
import difflib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spiritbox import listen, noise  # noqa: E402

HERE = Path(__file__).parent
# SPIRITBOX_SET=holdout: a second set of meetings, made and scored only after the prompt was settled
SET = "_" + os.environ["SPIRITBOX_SET"] if os.environ.get("SPIRITBOX_SET") else ""


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def label(seg, said):
    """real: the words match a line that was read near that time. ghost: nothing was being said."""
    t = norm(seg["text"])
    # Whisper's timestamps drift by a few seconds after a long pause; the same words that close are the real line.
    # An echo of a line said a minute earlier is still a ghost.
    if any(abs(seg["start"] - s["start"]) < 15 and difflib.SequenceMatcher(None, t, norm(s["text"])).ratio() >= 0.8
           for s in said):
        return "real"
    near = [s for s in said if seg["start"] < s["end"] + 2 and seg["end"] > s["start"] - 2]
    if not near:
        return "ghost"
    best = max(difflib.SequenceMatcher(None, t, norm(s["text"])).ratio() for s in near)
    # half a line counts: Whisper splits and merges sentences. Below that, it's words nobody said.
    return "real" if best >= 0.5 or any(t and t in norm(s["text"]) for s in near) else "ghost"


def main(sizes):
    meetings = json.loads((HERE / f"meetings{SET}.json").read_text())
    path = HERE / f"transcripts{SET}.json"
    out = json.loads(path.read_text()) if path.exists() else []  # resumable: memory on this laptop runs out now and then
    said = {m["name"]: m["said"] for m in meetings}
    for s in out:  # labels are cheap; transcripts aren't, so relabel what's saved
        s["truth"] = label(s, said[s["meeting"]])
    path.write_text(json.dumps(out, indent=1))
    done = {(s["model"], s["meeting"]) for s in out}
    for size in sizes:
        for m in meetings:
            if (size, m["name"]) in done:
                continue
            audio = noise.load(HERE / f"meetings{SET}" / f"{m['name']}.wav")
            segs = listen.retry(listen.transcribe, audio, guards=True, size=size, language="en")
            for i, s in enumerate(segs):
                s.update(meeting=m["name"], bed=m["bed"], model=size, i=i, truth=label(s, m["said"]))
            out += segs
            g = [s["text"] for s in segs if s["truth"] == "ghost"]
            print(f"{size:5} {m['name']:10} {len(segs):3} lines, {len(g)} ghosts {g[:4]}", flush=True)
            path.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:] or ["tiny", "base", "small"])
