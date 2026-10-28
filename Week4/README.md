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
  witness.py      Gemma 3 4B through Ollama, asking two questions about each line Whisper doubted
  __main__.py     the command line
eval/
  census.py       105 clips: 7 noises x 5 seeds x Whisper tiny, base, small, guards off
  make_meetings.py   six synthetic meetings: Windows voices read eval/lines.txt with pauses over six noise beds,
                  so we know exactly when somebody spoke
  transcribe_meetings.py   transcribes them the normal way and labels every line real or ghost
  judge.py        scores the rules against Gemma; Gemma's verdicts are cached in witness_cache.json
                  SPIRITBOX_SET=holdout runs any of these three on the held-out meetings (eval/lines_holdout.txt)
  export_web.py   packs the results for the page
web/              the demo page: whisper-tiny in the browser through transformers.js, the rules ported to JS
tests/            the rules, the noise generator, and the order the witness runs in
```

## Run it

Needs Python 3.11+, ffmpeg for audio files, and [Ollama](https://ollama.com) with `gemma3:4b` for the witness.

```
pip install -r requirements.txt
python -m spiritbox summon pink                 # what Whisper base hears in 30 s of pink noise
python -m spiritbox summon white --size small --seed 3
python -m spiritbox exorcise meeting.mp3        # normal transcript, rules first, then Gemma on the doubted lines
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

Six meetings, about five minutes each, transcribed with Whisper's normal settings (VAD and thresholds on), so we
know exactly when somebody spoke. Most ghosts are not the famous "Thanks for watching": they are **echoes**, an
earlier line written again minutes later during a long pause, sometimes reworded.

Gemma's prompt went through three versions on these meetings (195 lines, 12 ghosts):

| version | ghosts caught | real lines flagged |
|---|---|---|
| 1. Gemma reads every line and gives a verdict | 12 of 12 | 84 |
| 2. Gemma reads only the 23 lines Whisper itself doubted | 7 of 12 | 5 |
| 3. Same 23 lines, two yes/no questions instead of a verdict | 12 of 12 | 3 |

Version 1 suspected nearly every line after a pause. Version 2 wrote reasons like "a direct echo of the line at 27s"
and then answered "real". Version 3 asks *was this said earlier in the meeting?* and *is it a phrase that ends a
video?*, and the code turns the answers into the verdict. "Whisper doubted" means no-speech probability over 0.3 and
average log-probability under -0.5, the same cut-offs the prompt already used to describe Whisper's confidence.

Because version 3 was tuned on those meetings, it was then scored once on six new meetings: 30 sentences not used
before, new pauses, new noise, made after the prompt was settled (202 lines, 19 ghosts):

| judge | caught | missed | false alarms | precision | recall | F1 |
|---|---|---|---|---|---|---|
| the rules | 12 | 7 | 4 | 0.75 | 0.63 | 0.69 |
| Whisper's doubt alone (strike every doubted line) | 11 | 8 | 9 | 0.55 | 0.58 | 0.56 |
| Gemma on the doubted lines | 10 | 9 | 2 | 0.83 | 0.53 | 0.65 |
| **the rules, then Gemma** | **17** | **2** | **5** | **0.77** | **0.89** | **0.83** |

Neither judge is enough alone. The rules catch the stock phrases Whisper writes without doubting itself (Whisper
small wrote "You" seven times into one silent stretch); Gemma catches the reworded echoes no list can hold. That
combination is what `exorcise` runs. Every verdict, with Gemma's reason, is in `eval/judge_holdout.json`; the
earlier prompts' runs are kept in `eval/judge_first_prompt.json` and `eval/judge_second_prompt.json`.

## Limits

- 19 held-out ghosts is a small test set. The numbers are a direction, not a benchmark.
- The meetings are synthetic: Windows text-to-speech voices over generated noise, not people in a room.
- The rules were written before the evaluation; one later fix (a real "Thank you. Let's start" was read as a
  sign-off) changed no verdict in either set. Gemma's prompt was tuned on the first six meetings; only the
  held-out numbers are clean, and they come from one run.
- Gemma takes 10 to 20 seconds per line on a laptop CPU, but it only reads the lines Whisper doubted (about one in
  ten here), so a five-minute meeting takes well under a minute.
- The page runs whisper-tiny with transformers.js, which has no no-speech score, so only the text rules run there.
  Pink and brown noise on the page come from a filter, not the FFT the Python code uses.

## Credits

Whisper by OpenAI (MIT). Gemma 3 by Google (Gemma terms). faster-whisper by SYSTRAN, transformers.js by Hugging Face,
Ollama. Pictures on the page are from Wikimedia Commons; their credits are in the page footer and
`web/assets/credits.json`.

AI assistance was used for this project. I did the planning and laid the base foundations; the rest of the coding
was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that I am accountable
for the code.
