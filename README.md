# Hacktoberfest 2026

My work for the DEV Hacktoberfest Open-Source AI Challenge, one folder per week.

| week | theme | project |
|---|---|---|
| 1 | Touch Grass | [Proof of Grass](Week1/) |
| 2 | Side Hustle | [Déjà](Week2/) ([demo](https://deja-hacktoberfest.vercel.app)) |
| 3 | Slow and Steady | [Effort Budget](Week3/) ([demo](https://effort-budget.vercel.app)) |
| 4 | Ghost in the Machine | [Spirit Box](Week4/) ([demo](https://spirit-box-hacktoberfest.vercel.app)) |

## Week 1: Touch Grass

**What the challenge asked.** Build something with open-weight models or open-source AI at its core: running an
open model, building on an open agent framework, running inference locally, or all three. The week's theme was
"Touch Grass": get people off the screen and into the world (hiking, birding, gardening, runs). The post should say
why open innovation matters for the build, and bonus points go to anyone who takes it outside and reports back.

**What I built.** Proof of Grass: an offline bird-sound model (Google's Perch 2.0, Apache-2.0, run locally through
ONNX) judges whether a recording sounds alive, and the result is sealed into a hash-chained receipt that anyone can
verify without the model. Code, method, measured results and limits are in [Week1/README.md](Week1/README.md).

**Why open.** The model runs on a laptop with no internet and no account, the audio never leaves the machine, and
the verification step needs no model at all. Being open let me inspect the full label list, regroup it into
living / nature / human classes, and re-tune the decision rules after the evaluation exposed a flaw.

**AI disclosure.** AI assistance was used for this project. I did the planning and laid the base foundations; the
rest of the coding was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that
I am accountable for the code. Every number in the READMEs comes from the evaluation scripts in `Week1/eval/`. Not
tested outdoors yet.

## Week 2: Side Hustle

**What the challenge asked.** Build something on open-weight or open-source AI that someone would pay for.

**What I built.** Déjà: a memory of your own screen that you can talk to. It reads what is on screen every few
seconds with local OCR, keeps it in a search index on your disk, and answers questions like "what was that hotel I
looked at yesterday?" with the screenshot it came from. Say "remind me to..." and it keeps a reminder instead. Speech
is Whisper, answers are Gemma 3 1B through Ollama, all on the laptop. Details, privacy model and limits are in
[Week2/README.md](Week2/README.md).

**AI disclosure.** AI assistance was used for this project. I did the planning and laid the base foundations; the
rest of the coding was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that
I am accountable for the code.

## Week 3: Slow and Steady

**What the challenge asked.** Build something on open-weight or open-source AI around the theme of slowing down:
lazy, low-effort, Sloth Day energy.

**What I built.** Effort Budget: show it a photo of your room and say how much energy you have left, from 10 seconds
to 10 minutes. Gemma 3 4B lists what's lying around and how long each thing takes to put away; a small submodular
planner picks the moves worth the most tidiness for exactly that budget and hands you just one, with a timer. It
learns how long things really take you, and judges an after photo against the before. Details, measurements and
limits are in [Week3/README.md](Week3/README.md).

**AI disclosure.** AI assistance was used for this project. I did the planning and laid the base foundations; the
rest of the coding was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that
I am accountable for the code.

## Week 4: Ghost in the Machine

**What the challenge asked.** Build something on open-weight or open-source AI around the theme of ghosts: things
that haunt machines, or machines that seem to have a life of their own.

**What I built.** Spirit Box: OpenAI's open Whisper with every filter that keeps it quiet switched off, played pure
noise. It talks, and it says the same few phrases across seeds and model sizes. A census of 105 noise clips is on the
demo page, which also runs Whisper tiny in the browser so anyone can summon one. The useful half: Gemma 3 4B, local,
reads the lines Whisper itself doubted in an ordinary meeting transcript and points at the ones nobody said.
Details, measurements and limits are in [Week4/README.md](Week4/README.md).

**AI disclosure.** AI assistance was used for this project. I did the planning and laid the base foundations; the
rest of the coding was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that
I am accountable for the code.
