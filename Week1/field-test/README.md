# Field test

Three WhatsApp recordings, scored with `python -m trailear listen <clip> --dry`
(Perch 2.0, default thresholds, nothing tuned on these).

| clip | what it is | length | verdict | margin (pass at 3) | strongest human-made sound |
|---|---|---|---|---|---|
| humans are snart (inside).ogg | me talking at my desk | 12.1 s | INCONCLUSIVE | 1.23 | Human_voice |
| outside.ogg | a walk, birds and traffic | 27.8 s | INCONCLUSIVE | 2.53 | Vehicle, crumpling |
| grass is bad (outside).mpeg | a second outdoor take, birds and traffic | first 125 s scored | INCONCLUSIVE | 2.43 | Vehicle, engine, horn |

The first outside clip missed the pass mark by 0.47 and the second by 0.57. Its top bird guesses were hoopoe,
rose-ringed parakeet and starling, which I haven't verified by ear.

Voice notes are Opus-compressed for speech, which probably drops faint bird sound.
A raw recording might score higher; I haven't tried it.

The second outdoor clip had a confident American robin (logit 12.3) but traffic outweighed it. The engine only reads the first 125 s of a file.
