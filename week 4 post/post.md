---
title: I played static to Whisper. It said it was going to the next room.
published: false
cover_image: https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week4/docs/cover.png
tags: devchallenge, hf26challenge, gemma, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

## What I Built

**Spirit Box** turns off every filter that keeps OpenAI's open Whisper quiet, then plays it pure noise. It talks. Silence gets "you", every time. Mains hum gets *"I'm going to go to the next room."*, eleven times a clip. It never leaves.

Those ghosts also turn up in real transcripts with normal settings ([Koenecke et al., 2024](https://arxiv.org/abs/2402.08021) found them in about 1% of clips), where they look like every other line. So the second half is a **witness**: Gemma 3 4B, running locally, reads a meeting transcript and points at the lines nobody said.

## Demo

**Live: https://spirit-box-hacktoberfest.vercel.app**. Pick a noise, press Summon, and Whisper tiny listens in your browser tab. No audio leaves it.

![In mains hum, Whisper tiny heard "(sizzling)"](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week4/docs/summon.png)

```
$ python -m spiritbox exorcise meeting.wav
      [ 257.4s] Please don't merge anything after 5 today.
GHOST [ 287.4s] Please don't merge anything.  <- echo: repeats a line said earlier
GHOST [ 305.4s] Please don't merge anything.  <- repetition loop: a rule matched
```

Nobody spoke after 4:20. The ghost just had strong opinions about merges.

## Code

{% github Phantom8420/Hacktoberfest %}

## How I Built It

**The census.** 7 noises × 5 seeds × 3 Whisper sizes = 105 clips. All 105 said something. The same phrases come back across seeds, so they come from the training data, not the noise. Most noise is detected as Norwegian Nynorsk, which I can't explain beyond Norway being very quiet.

![What each model size heard in each noise](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week4/docs/census.png)

**The meetings.** Windows voices read 30 meeting lines with long pauses over six noise beds, so I know exactly when someone spoke. Most ghosts weren't "Thanks for watching". They were **echoes**: an earlier line written again in a later silence. Whisper is the colleague who repeats your point five minutes later.

**Gemma, three tries.** Reading every line, it flagged 84 real ones: a paranoid intern. Reading only the lines Whisper doubted, it would write "this is a direct echo" and then answer **real**. So I stopped asking for a verdict. It now answers two yes/no questions (*said earlier?* *a video sign-off?*) and the code decides. Gemma is a good witness; it just shouldn't be the judge.

**Held out.** Scored once on six new meetings:

| judge | caught (of 19) | false alarms | F1 |
|---|---|---|---|
| rules | 12 | 4 | 0.69 |
| Gemma | 10 | 2 | 0.65 |
| **rules, then Gemma** | **17** | **5** | **0.83** |

They miss different things: rules catch stock phrases, Gemma catches reworded echoes. It runs on a laptop with no GPU, at 10–20 s per doubted line. Limits: 19 ghosts is small, and the meetings are synthetic speech.

## The Spirit of It

I expected noise to give garbage. Instead every clip gave a calm, grammatical sentence, and the same one came back from different seeds, as if the static had a script. Fifty-six copies of "I'm going to go to the next room" is the closest I've come to a haunting.

## Why Does Open Innovation Matter?

No hosted API has a "please hallucinate" checkbox. Turning the filters off only works because the weights and the decoding loop are on my disk, and the witness reads private meetings without them leaving the machine. But the training data isn't open, so nobody outside OpenAI can say why it wants the next room. Open weights let you meet the ghost; open data would tell you where it's buried.

## Prize Categories

**Best Use of Gemma.** Gemma 3 4B, local through Ollama, is the witness. It answers in a strict JSON schema, and it's measured against a rules baseline on held-out meetings, failed prompts included.

---

AI assistance was used for this project. I did the planning and laid the base foundations; the rest of the coding was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that I am accountable for the code.
