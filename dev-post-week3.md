---
title: Effort Budget: the most tidiness for 30 seconds of energy, picked by Gemma and a submodular planner
published: false
cover_image: https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week3/docs/cover.png
tags: devchallenge, hf26challenge, gemma, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

Every tidying app I've seen assumes you have energy. Checklists, routines, streaks. On a Sloth Day you don't. You
have maybe 30 seconds in you, and the real question is which 30 seconds.

**Effort Budget** answers exactly that. Take a photo of your room and slide the energy bar somewhere between
"barely alive" (10 seconds) and "suspiciously motivated" (10 minutes). Gemma 3 looks at the photo and lists what's
lying around, where each thing goes, how long it takes and how much it would help. A small planner picks the moves
worth the most tidiness for exactly your budget, and the page shows you **one** of them, big, with a timer:

![The app: Gemma's item list, the energy slider and the one move](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week3/docs/app.png)

> **Plastic bottles**, from the floor to the bin, about 30 seconds. *Start.*

That's the whole ask. The full plan is there if you want it. Two more things make it more than a prompt:

- **It learns your speed.** The timer records how long moves really take you, per destination (bin runs are quick,
  laundry never is), and the next plan uses your seconds instead of Gemma's guesses.
- **It checks the result.** Take an after photo from the same spot and Gemma judges whether the room actually got
  tidier, asked twice with the photos swapped, because small vision models play favourites with photo order. If it
  can't decide, it says so and shows you what it counted.

Everything runs on your own computer. Photos stay in memory, get their GPS-carrying EXIF stripped before the model
sees them, and are never saved.

![Effort Budget on a phone, light theme](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week3/docs/phone.png)

## Demo

**Try it:** https://effort-budget.vercel.app (the app itself is at [/try.html](https://effort-budget.vercel.app/try.html)), with three sample rooms from Wikimedia Commons. A web page can't run Gemma,
so the demo replays what Gemma 3 4B saw in each room on my laptop; the planner and the time learning run live in your
browser.

![Pick a room, items appear one by one as Gemma writes them, untick one, set your energy, get one move with a countdown](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week3/eval/charts/demo.gif)

*The demo replaying Gemma's real output for the dorm room, sped up: locally the items arrive over about 100 seconds.*

![The front page of the demo site](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week3/docs/home.png)

![How it goes: photo, fix the list, set your energy, one move](https://raw.githubusercontent.com/Phantom8420/Hacktoberfest/main/Week3/docs/steps.png)

<!-- Optional before publishing: swap in a before/after pair of your own room (photos/raw/pairs/, python eval/judge_pairs.py) -->

## Code

{% github Phantom8420/Hacktoberfest %}

The project is in [`Week3/`](https://github.com/Phantom8420/Hacktoberfest/tree/main/Week3): plain Python
standard library for the server, Pillow for photos, vanilla JS for the page, 20 tests.

The photo is usually on your phone, not the laptop running Gemma, so `python -m effort --phone` puts a QR code on the
page. Scan it and the phone becomes the camera and the screen while Gemma stays on the laptop; anything that isn't
the laptop needs the random key inside that code.

## How I Built It

**Gemma only looks.** Gemma 3 4B runs through Ollama and answers in a fixed JSON schema: what, which zone, where it
goes (forced into a short list: bin, laundry, wardrobe, shelf, drawer, sink, desk-side, other), seconds, and mess
1-5. Everything it returns is clamped and deduplicated. Then you tap away anything it imagined. Small models invent
things, and a plan built on a sock that isn't there is worse than no plan.

**Code decides.** Tidiness isn't additive: clearing the first thing off a desk changes how the room looks more than
clearing the fifth. So a zone's value is (its cleared mess)^0.7, summed over zones. That makes the plan a budgeted
monotone submodular maximisation, which sounds grand and mostly means "biggest mess first" is wrong more often than
you'd think. Rooms of up to 16 items get the exact best plan by trying every subset (0.2 s); above that, cost-benefit
greedy with a single-best-item fallback is guaranteed at least (1 - 1/e)/2 of the best.

On Gemma's real item lists (27 of them, from 9 photos) biggest-mess-first was worse than the exact plan in 35% of
cases, 62% of the best at worst. It matters more in bigger rooms;
against the exact plan on 1,000 random rooms of 3 to 14 items, at 30 s, 90 s and 5 minutes:

| | plans worse than the best | worst case | average |
|---|---|---|---|
| greedy | 18% | 66% of the best | 98.8% |
| biggest mess first | 32% | 30% of the best | 94.4% |

**Your seconds, not the model's.** Per destination it keeps (sum of actual/guess + 2) / (moves + 2): two imaginary
moves at exactly 1.0 are mixed in, so one slow trip to the laundry can't swing the whole plan.

**How well does Gemma see?** Shown the same photo three times (slightly cropped or darkened), its item lists overlap
by about 61%, and the one move comes out the same in all three for only 2 to 4 of 9 photos. That's why you fix the
list before planning. The before/after judge, shown two takes of an unchanged room, said "same" 7 times out of 9
and "unclear" twice; the photo swap caught the one time it leaned toward whichever photo came second. It never
claimed a change that wasn't there.

On a real clean-up, though, the side-by-side comparison failed in an instructive way: Gemma called the right-hand photo
tidier every single time, whichever photo was on the right. The swap turned that into "unclear" instead of a
confident wrong answer. The recount got it (9 things lying around before, 3 after), but item counts also drift on
rooms that didn't change, so when the comparison can't decide the app shows you both counts and lets you call it.
A 4B model is a fine pair of eyes and a poor referee.

**Slow, on purpose.** On an i5 laptop with no GPU, one photo takes about two minutes. I kept it that way rather than
calling a hosted model, because the input is a photo of the inside of someone's home. The theme helped: a sloth app
that makes you wait two minutes is on brand. The wait isn't dead time, though: Gemma's reply streams, every finished
item appears as a chip straight away, and you untick its inventions and set your energy while it's still looking.

One thing I didn't expect: the model wouldn't load at all at first, with `failed to allocate CPU buffer` and 14 GB of
RAM free. The laptop has no page file, so Windows ran out of *commit* memory, not RAM. Memory-mapping the weights and
turning off llama.cpp's weight repacking (`LLAMA_ARG_REPACK=false`) took it from failing to loading in 7 seconds.

## Why Does Open Innovation Matter?

Because the input is a photo of your bedroom. With open weights the model runs where the photo already is, and the
photo never has to go anywhere. Open weights also meant I could test the model's failure modes properly: run the same
room again and again to see what it invents, and swap the before/after order to catch it favouring the first photo,
without paying per call or wondering whether the model behind an API changed overnight.

## Prize Categories

**Best Use of Gemma.** Gemma 3 4B is the eyes of the app, run locally through Ollama: it reads the room, estimates
effort and payoff in a strict JSON schema, and judges the before/after pair. The design treats it as a capable but
fallible witness: its answers are clamped, the user vetoes hallucinations, the swap test catches order bias, and the
evaluation scripts measure how stable it is.

---

AI assistance was used for this project. I did the planning and laid the base foundations; the rest of the coding
was done by a team of AI agents led by Claude (Anthropic). I left the debugging for myself so that I am accountable
for the code.
