# Field test

Two WhatsApp voice notes, scored with `python -m trailear listen <clip> --dry`
(Perch 2.0, default thresholds, nothing tuned on these).

| clip | what it is | length | verdict | margin (pass at 3) | strongest human-made sound |
|---|---|---|---|---|---|
| inside.ogg | me talking at my desk | 12.1 s | INCONCLUSIVE | 1.23 | Human_voice |
| outside.ogg | a walk, birds and traffic | 27.8 s | INCONCLUSIVE | 2.53 | Vehicle, crumpling |

The outside clip missed the pass mark by 0.47. Its top bird guesses were hoopoe,
rose-ringed parakeet and starling, which I haven't verified by ear.

Voice notes are Opus-compressed for speech, which probably drops faint bird sound.
A raw recording might score higher; I haven't tried it.
