---
title: Spirit Box: Whisper hears voices in pure noise, and Gemma points at the lines nobody said
published: false
cover_image: https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week4/docs/cover.png
tags: devchallenge, hf26challenge, gemma, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

## What I Built

In the 1950s people left tape recorders running in empty rooms and tuned radios between stations, then listened to
the hiss for voices. A spirit box is the modern version: a radio sweeping the dial with the squelch off.

I built one for a speech model. **Spirit Box** takes OpenAI's open Whisper, switches off everything that keeps it
quiet (the voice-activity filter, the no-speech threshold, the repetition check), and plays it static. It talks.
Thirty seconds of digital silence gets "you" from every model size and every seed. A mains hum gets *"I'm going to
go to the next room."*, eleven times a clip, and the bigger model hears Welsh in the same hum. In hiss and rumble it
writes a hundred copies of one Sinhala letter and calls the language Norwegian.

That's the spooky half. The useful half is that these ghosts don't only appear when you go looking. Whisper, with its
normal settings, still writes sentences nobody said into the quiet parts of real recordings
([Koenecke et al., 2024](https://arxiv.org/abs/2402.08021) found them in about 1% of real clips), and they look exactly
like every other line. So the second part of Spirit Box is a **witness**: Gemma 3 4B, running locally, reads an
ordinary meeting transcript line by line and points at the ones that were never spoken, with a reason.

## Demo

**Live page: https://spirit-box-hacktoberfest.vercel.app**

Pick a noise and press Summon. Whisper tiny downloads into your browser tab (about 40 MB, through transformers.js),
listens to 30 seconds of noise made right there, and writes down what it hears. The page also shows the census and
walks through cleaning a meeting transcript.

![The summon box on the page](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week4/docs/summon.png)

From the command line:

```
$ python -m spiritbox summon hum
[   0.0s] I'm going to go to the next room.  (en, no_speech 0.99)
[   2.0s] I'm going to go to the next room.  (en, no_speech 0.99)
[   4.0s] I'm going to go to the next room.  (en, no_speech 0.99)
...
[  26.0s] I'm going to go to the next room.  (en, no_speech 0.99)
[  28.0s] you  (en, no_speech 0.81)

$ python -m spiritbox exorcise meeting.wav
      [   0.0s] I moved the stand up to half past 9.
      [  21.4s] The budget for the offsite is about half of last years.
      ...
      [ 227.4s] I think the bug is in the date parsing.
      [ 257.4s] Please don't merge anything after 5 today.
GHOST [ 287.4s] Please don't merge anything.  <- echo: The line repeats a very similar phrase that was stated earlier in the meeting, indicating a hallucination by Whisper.
GHOST [ 305.4s] Please don't merge anything.  <- repetition loop: a rule matched
```

That meeting is one of the held-out ones: a fan under five minutes of talk, and nobody spoke after 4:20.

## Code

{% github Phantom8420/Hacktoberfest %}

Everything for this week is in [`Week4/`](https://github.com/Phantom8420/Hacktoberfest/tree/main/Week4): the
package, the evaluation scripts with their saved results, and the page.

## How I Built It

**The census.** Seven kinds of generated noise (silence, white, pink, brown, mains hum, fan, rain), five seeds each,
through Whisper tiny, base and small with the guards off: 105 clips. All 105 produced text, 214 lines between them.
The same phrases come back across seeds and across model sizes:

| what Whisper wrote | times |
|---|---|
| I'm going to go to the next room. | 56 |
| you | 22 |
| I'm going to do it. | 14 |
| Ysbydd yw'r cyllid yma. (Welsh) | 14 |
| 2.5% de rupo. | 13 |

Most of these come from one noise and one model size each: the "next room" loop is Whisper base in mains hum, the
Welsh is Whisper small in the same hum. Most noise gets detected as Norwegian Nynorsk, level with English. Nothing in the noise carries those words; they
come from what the model was trained on, and we can only guess at that, because the weights are open and the
training data isn't.

**The meetings.** To measure ghosts you need to know exactly when somebody spoke. I wrote 30 ordinary meeting
lines, had Windows' built-in voices read them with long pauses over six noise beds (silence, a quiet room, a fan,
mains hum, rain, pink noise), and transcribed the result the normal way, filters on. Anything written during a pause
is a ghost. They're not what I expected: only a few are the famous "Thanks for watching". Most are **echoes**, an
earlier sentence written again minutes later during a long silence, sometimes reworded ("We should write down why we
picked this database" comes back as "I'll write down why we picked this database").

**The rules.** The baseline is what a careful engineer would write: a list of known sign-offs, sound tags like
"(music)", repetition loops, wrong language, and lines Whisper itself scored as probably silence. On the first six
meetings they caught 4 of 12 ghosts. They can't catch an echo: it's a normal sentence with normal-looking scores.

**Gemma, three tries.** Gemma 3 4B runs through Ollama and can't hear the audio, so it judges the way a person reading
the transcript would: the line, the three either side, the pause before it, Whisper's confidence turned into words,
and any earlier line it closely resembles. It answers in a JSON schema.

| prompt | ghosts caught (of 12) | real lines flagged (of 183) |
|---|---|---|
| 1. read every line, give a verdict | 12 | 84 |
| 2. read only the 23 lines Whisper doubted, give a verdict | 7 | 5 |
| 3. same 23 lines, answer two yes/no questions | 12 | 3 |

The first try was useless: any line after a pause looked suspicious to it. Narrowing it to the lines Whisper itself
doubted (no-speech probability over 0.3 and log-probability under -0.5) fixed the false alarms but exposed a stranger
failure: Gemma would write *"the line is a direct echo of the line at 27s"* and then answer **real**. The fix was to
stop asking for a verdict at all. The third prompt asks *was this said earlier in the meeting?* and *is it a phrase
that ends a video?*, and the code turns the two answers into the verdict.

**The held-out test.** All of that was tuned on the same six meetings, so the third row flatters it. After the prompt
was settled I made six more with 30 new sentences, new pauses and new noise, and scored everything once:

| judge | caught (of 19) | false alarms (of 183) | F1 |
|---|---|---|---|
| the rules | 12 | 4 | 0.69 |
| Whisper's doubt alone | 11 | 9 | 0.56 |
| Gemma on the doubted lines | 10 | 2 | 0.65 |
| **the rules, then Gemma** | **17** | **5** | **0.83** |

Gemma alone dropped from the tuned number, which is the honest result. But the two judges miss different things.
The rules catch the stock phrases Whisper writes without doubting itself (Whisper small wrote "You" seven times into
one silent stretch, confident every time); Gemma catches the reworded echoes no list can hold. Together they catch 17
of 19. That combination is what the command line runs.

**Running it on a laptop.** The laptop has no GPU and no page file. Gemma loaded only after memory-mapping the
weights and turning off llama.cpp's weight repacking (`LLAMA_ARG_REPACK=false`); then it takes 10 to 20 seconds a
line. Because it only reads the lines Whisper doubted, about one line in ten here, a five-minute meeting is checked in
well under a minute.

**Honest limits.** Nineteen held-out ghosts is a small test, so these numbers are a direction, not a benchmark, and
they come from one run. The meetings are text-to-speech over generated noise, not people in a room. The rules were
written before any of this; the one change since, so "Thank you. Let's start" no longer counts as a sign-off, moved
no verdict in either set.

## Why Does Open Innovation Matter?

You can't do this to a closed model. Turning off the filters means passing `vad_filter=False` and three `None`
thresholds to faster-whisper, which only works because the model and the decoding loop are on my disk. The census
needed 105 runs and the evaluation hundreds of Gemma calls across three prompts; locally that costs nothing and gives the same answer
twice. And the thing being checked is a transcript of a private meeting, which is exactly what shouldn't leave the
machine: the witness runs where the recording already is.

There's a second point the project makes by accident. The weights are open, so anyone can reproduce these ghosts
in a browser tab. The training data is not, so nobody outside OpenAI can say for certain why it says *"I'm going to
go to the next room."*

## Prize Categories

**Best Use of Gemma.** Gemma 3 4B is the witness: run locally through Ollama, it reads the transcript lines Whisper
doubted, with their context, and answers two yes/no questions and a reason in a strict JSON schema. It is measured
against a rules baseline on held-out meetings, the two prompts that didn't work are reported too, and its misses and
false alarms are shown on the page.

---

AI assistance was used for this project. I did the planning and laid the base foundations; the rest of the coding
was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that I am accountable
for the code.
