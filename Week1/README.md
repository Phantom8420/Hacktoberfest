# Proof of Grass

Record or upload a few seconds of outside. A bird-sound model running **on your machine** decides whether
it sounds like nature, and the result is sealed into a hash-chained receipt that anyone can verify offline.
If you try to reuse the same recording (quieter, trimmed, re-encoded) the ledger recognises it and zeroes the score.

Built for the DEV Hacktoberfest Open-Source AI Challenge, "Touch Grass" week.

## How it works

1. **Listen.** [Perch 2.0](https://huggingface.co/justinchuby/Perch-onnx) (Apache-2.0, ONNX) scores each 5 s window
   against ~14,800 classes: bird/animal species, plus 198 FSD50k sound-event classes.
2. **Margin.** Per window: `max(best species logit, wild-class logit + 1.5) - strongest human-made class`.
   Species, frogs, insects, crows etc. count as life; rain, wind, streams count as nature but not as life;
   dogs, footsteps, fire are ambiguous and ignored; everything else (speech, engines, music, sirens) is human.
3. **Verdict.** Mean margin >= 3 -> `TOUCHED_GRASS` (human sound < 6.5) or `GRASS_PLUS_NOISE`. Otherwise, if nature
   classes beat human ones by >= 0.5 -> `AMBIENT_NATURE` (rain, waves, thunder: nothing alive, no score).
   Strong human sound (>= 8.5) with nature far below it (<= -3.5) and margin < 0 -> `HUMAN_MADE`. Else `INCONCLUSIVE`.
4. **Receipt.** Verdict, score, species heard, audio SHA-256 and an audio landmark fingerprint are appended to
   `trailear.ledger.jsonl`, each entry hashing the previous one.
5. **Replay check.** Shazam-style offset voting: peak-pair hashes from the new clip are matched against every earlier
   receipt, and >= 8 hashes agreeing on one time shift marks it `REPLAY` with score 0.

## Run it

```bash
pip install -r requirements.txt
# model: download perch_v2.onnx (~410 MB) from https://huggingface.co/justinchuby/Perch-onnx
export TRAILEAR_MODEL=/path/to/perch_v2.onnx      # or put it at models/perch_v2.onnx
python -m trailear listen walk.ogg --note "park, 7am"
python -m trailear verify trailear.ledger.jsonl    # no model needed
python -m trailear anchor trailear.ledger.jsonl    # prints the head hash: publish it
python -m trailear verify trailear.ledger.jsonl --anchor HASH
python -m trailear serve                           # http://127.0.0.1:8765
python -m pytest tests
```

Labels: `data/perch_labels.csv` comes from the `cgeorgiaw/Perch` Space label list.

## Measured results

`eval/run_eval.py` on 560 ESC-50 clips (Piczak, CC BY-NC 4.0, not redistributed; `eval/fetch_esc50.py`).
Groups were fixed before scoring: life (birds, crow, frog, insects, crickets), ambient (rain, waves, wind,
thunder, water, fire), human (16 machine/voice classes). Thresholds from my first 26 Wikimedia clips accused 85/140
ambient clips of being `HUMAN_MADE`, so the `AMBIENT_NATURE` and `HUMAN_MADE` rules were re-fit on **folds 1-2 only**.
Folds 3-5 were not looked at until the rules were frozen.

| folds 3-5 (untouched) | n | grass | ambient | inconclusive | human-made |
|---|---|---|---|---|---|
| life | 60 | 51 | 0 | 9 | 0 |
| ambient | 84 | 3 | 39 | 42 | 0 |
| human | 192 | 1 | 1 | 57 | 133 |

Insects are the weak spot (4/12 grass, 8 inconclusive). Wind, fire and pouring water mostly stay inconclusive.
The one human clip scored as grass is an airplane.

Replay (all 560 clips attacked, votes at the median): gain x0.3 63, 22 kHz round trip 73, 20 dB noise 55,
lowpass 4k 48, trim 1.7 s 32. Different recordings (34,168 pairs): max 6 votes, so the bar is 8. Weak cases:
10 dB noise (5th percentile 2 votes) and room reverb + noise (median 2) are **not** reliably caught.

Latency: about 0.2 s per 5 s window on a laptop CPU, no GPU.

## Limits (read these)

- ESC-50 clips are 5 s, zero-padded, and the rules were tuned on part of that same set. Folds 3-5 are clean for the
  new rules only, not for the whole design.
- Recall is partial (51/60 life). It refuses rather than guesses.
- Logits are uncalibrated and the thresholds are hand-set.
- Playing a bird recording through a speaker near the mic will score as grass unless you have already
  recorded that same clip. Different recordings of the same species are not recognised as replays.
- The ledger is tamper-evident, not tamper-proof. Someone who rewrites the whole file can rebuild the chain.
  Run `anchor` and publish the hash somewhere you cannot edit (a post, a commit); `verify --anchor HASH` then fails
  if the chain was rewritten afterwards. Without a published anchor, a full rewrite is undetectable.
- No field test has been done: every number above is from clips, not walks outside.
- The model is ~410 MB, so this is a local app, not a phone page.

## Credits

Perch 2.0 by Google DeepMind (Apache-2.0), ONNX export by `justinchuby/Perch-onnx`. Test clips: see CREDITS.md.
