# Spirit Box

A spirit box is a radio swept between stations with the squelch off, so people can listen for voices in the static.
This is the same idea pointed at a speech model: OpenAI's Whisper (open weights) with every filter that keeps it
quiet switched off, played pure noise. It talks. Then the useful half: Gemma 3 4B, running locally, reads ordinary
meeting transcripts and points at the lines nobody said.

Demo page: summon a ghost in your own browser, read the census, and watch a transcript get cleaned.
https://spirit-box-hacktoberfest.vercel.app

## Why this matters

Whisper is trained never to leave a pause empty. In 2024, Koenecke et al. ("Careless Whisper: Speech-to-Text
Hallucination Harms", ACM FAccT) found that about 1% of transcriptions of real speech contained whole sentences
nobody said, many of them during pauses. Meeting notes, captions and medical scribes are built on this model. The
lines it makes up look like every other line.

## What's here

```
spiritbox/        the package
  noise.py        seven kinds of generated noise: silence, white, pink, brown, mains hum, fan, rain
  listen.py       faster-whisper two ways: as everyone uses it, and with its guards off
  ghosts.py       the rules a careful engineer would write: known sign-offs, sound tags, loops, wrong language,
                  and lines Whisper itself scored as probably silence
  witness.py      Gemma 3 4B through Ollama, judging each line from its neighbours, its timing and Whisper's numbers
  __main__.py     the command line
eval/
  census.py       105 clips: 7 noises x 5 seeds x Whisper tiny, base, small, guards off
  make_meetings.py   six synthetic meetings: Windows voices read eval/lines.txt with pauses over six noise beds,
                  so we know exactly when somebody spoke
  transcribe_meetings.py   transcribes them the normal way and labels every line real or ghost
  judge.py        scores the rules against Gemma; Gemma's verdicts are cached in witness_cache.json
  export_web.py   packs the results for the page
web/              the demo page: whisper-tiny in the browser through transformers.js, the rules ported to JS
tests/            the rules and the noise generator
```

## Run it

Needs Python 3.11+, ffmpeg for audio files, and [Ollama](https://ollama.com) with `gemma3:4b` for the witness.

```
pip install -r requirements.txt
python -m spiritbox summon pink                 # what Whisper base hears in 30 s of pink noise
python -m spiritbox summon white --size small --seed 3
python -m spiritbox exorcise meeting.mp3        # normal transcript, each line judged by Gemma
python -m spiritbox exorcise meeting.mp3 --judge rules
pytest
```

`summon` appends every contact to `contacts.jsonl`.

## Results

### Census: every clip said something

105 clips, 30 seconds each, guards off. All 105 produced text; 214 lines between them (tiny 35, base 119, small 60).

| what Whisper wrote | times |
|---|---|
| I'm going to go to the next room. | 56 |
| you | 22 |
| I'm going to do it. | 14 |
| Ysbydd yw'r cyllid yma. (Welsh) | 14 |
| 2.5% de rupo. | 13 |
| 1.5mm x 2.5mm x 2.5mm x ... (a loop) | 11 |

Silence gives "you" from every model and every seed. The "next room" loop is Whisper base in mains hum (about eleven
times a clip, every seed); the Welsh is Whisper small in the same hum. Most noise is detected as Norwegian Nynorsk
(93 of 214 lines, level with English at 93). In hiss and rumble the small model writes long runs of a single
Sinhala, Khmer or Georgian letter, while still calling the language Nynorsk. The same phrases come back across seeds and models, which says they come from the training data
rather than from the noise.

### Witness: who catches the ghosts in a normal transcript

Six meetings, about five minutes each, transcribed with Whisper's normal settings (VAD and thresholds on). 195 lines;
12 of them are ghosts: three YouTube sign-offs, and nine plausible sentences, mostly echoes of something said
minutes earlier, written during long pauses.

WITNESS_TABLE

The rules catch sign-offs and nothing else: the echoes and invented lines carry normal confidence scores, so no
threshold separates them. Gemma gets a hint the rules don't: when a line closely matches one said earlier, the
earlier line is shown to it.

## Limits

- 12 ghosts is a small test set. The numbers are a direction, not a benchmark.
- The meetings are synthetic: Windows text-to-speech voices over generated noise, not people in a room.
- The rules were written before the evaluation and not tuned on it; Gemma's prompt was adjusted on a handful of
  lines from these meetings, so its score is optimistic.
- Gemma takes 10 to 20 seconds per line on a laptop CPU. A one-hour meeting is too slow for real time.
- The page runs whisper-tiny with transformers.js, which has no no-speech score, so only the text rules run there.
  Pink and brown noise on the page come from a filter, not the FFT the Python code uses.

## Credits

Whisper by OpenAI (MIT). Gemma 3 by Google (Gemma terms). faster-whisper by SYSTRAN, transformers.js by Hugging Face,
Ollama. Pictures on the page are from Wikimedia Commons; their credits are in the page footer and
`web/assets/credits.json`.

AI assistance was used for this project. I did the planning and laid the base foundations; the rest of the coding
was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that I am accountable
for the code.
