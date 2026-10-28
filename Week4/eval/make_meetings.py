"""Recordings where we know exactly when someone spoke: Windows' built-in voices read eval/lines.txt with pauses of
noise in between. Whatever Whisper writes during a pause is a ghost. Writes eval/meetings/*.wav and meetings.json.

    python eval/make_meetings.py      # Windows only (System.Speech); a minute or two
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spiritbox import noise  # noqa: E402

HERE = Path(__file__).parent
# SPIRITBOX_SET=holdout: a second set of meetings, made and scored only after the prompt was settled
SET = "_" + os.environ["SPIRITBOX_SET"] if os.environ.get("SPIRITBOX_SET") else ""
OUT = HERE / f"meetings{SET}"
VOICES = ["Microsoft David Desktop", "Microsoft Zira Desktop", "Microsoft Hazel Desktop"]
BEDS = ["silence", "room", "fan", "hum", "rain", "pink"]  # "room" is quiet white noise, like a laptop mic in a still room


def speak(lines, folder):
    """One wav per line, read by rotating voices."""
    ps = ["Add-Type -AssemblyName System.Speech", "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
          "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, 'Sixteen', 'Mono')"]
    for i, line in enumerate(lines):
        ps += [f"$s.SelectVoice('{VOICES[i % len(VOICES)]}')", f"$s.SetOutputToWaveFile('{folder}\\{i}.wav', $f)",
               f"$s.Speak('{line.replace(chr(39), chr(39) * 2)}')"]
    ps.append("$s.SetOutputToNull()")
    subprocess.run(["powershell", "-NoProfile", "-Command", "; ".join(ps)], check=True)
    return [noise.load(Path(folder) / f"{i}.wav") for i in range(len(lines))]


def bed(kind, n, seed):
    if kind == "room":
        return 0.004 * np.random.default_rng(seed).standard_normal(n).astype(np.float32)
    return 0.25 * noise.make(kind, n / noise.SR + 1, seed)[:n]


def main():
    lines = [x for x in (HERE / f"lines{SET}.txt").read_text(encoding="utf8").splitlines() if x.strip()]
    with tempfile.TemporaryDirectory() as tmp:
        clips = speak(lines, tmp)
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(8 if SET else 7)
    meetings = []
    for m, kind in enumerate(BEDS):
        order = rng.permutation(len(lines))[:10]
        parts, said, t = [], [], 0.0
        for i in order:
            gap = int(rng.uniform(4, 40) * noise.SR)  # long pauses are where Whisper starts making things up
            parts += [np.zeros(gap, np.float32), clips[i]]
            said.append({"start": round(t + gap / noise.SR, 2), "end": round(t + (gap + len(clips[i])) / noise.SR, 2),
                         "text": lines[i]})
            t += (gap + len(clips[i])) / noise.SR
        tail = int(rng.uniform(20, 40) * noise.SR)
        speech = np.concatenate(parts + [np.zeros(tail, np.float32)])
        audio = speech + bed(kind, len(speech), m + (100 if SET else 0))
        name = f"{m}_{kind}"
        (OUT / f"{name}.wav").write_bytes(noise.wav(audio))
        meetings.append({"name": name, "bed": kind, "seconds": round(len(audio) / noise.SR, 1), "said": said})
        print(name, meetings[-1]["seconds"], "s")
    (HERE / f"meetings{SET}.json").write_text(json.dumps(meetings, indent=1))


if __name__ == "__main__":
    main()
