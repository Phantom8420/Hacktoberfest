# Thud

Drop a coin on each floor tile, let the laptop listen, and get a map of the tiles that came loose underneath.
A hollow (debonded) tile rings lower and longer than one sitting on its adhesive bed. Inspectors find them by ear
with a tapping hammer. Thud does the same on every tile, then keeps a receipt nobody can quietly edit.

Who it is for: home inspectors who want a map instead of a hunch, and renters or new owners who want proof of the
floor on the day they got the keys.

## How it works

1. **Tap.** Record one row at a time (phone or laptop mic, or upload a recording). `thud/taps.py` finds each
   tap with a 1 ms envelope and adaptive threshold and measures seven loudness-independent features: peak
   frequency, spectral centroid and roll-off, energy below 1 kHz, decay time to -20 dB, ring ratio (energy after
   30 ms over the first 30 ms) and spectral flatness.
2. **Confirm.** Before any labels, tiles are ranked by how unusual they sound on this floor (robust z-score,
   median/MAD). You check the top few by hand and mark at least two solid and two hollow.
3. **Score.** TabPFN (Prior Labs, open weights) learns this floor in-context from those few labels and scores
   every other tile. No training run, no model trained on someone else's floor.
4. **Report.** Gemma 3 4B, run locally through Ollama, writes the summary and next steps, and describes your
   photos. The flagged-tile list and photo count are written by code, never by the model, so a report can't list
   a tile or a photo that isn't there. If Ollama is not running, a plain template writes it instead and says so.
5. **Receipt.** Each report is sealed into a hash-chained ledger with the tile features, the photo hashes and
   the report hash. `python -m thud verify thud.ledger.jsonl --anchor HASH` fails if anything was changed.

Audio, photos and reports stay on the machine. Only if local TabPFN can't load does Thud fall back to the
TabPFN API, which receives the numeric tap features and nothing else.

## Run it

```bash
pip install -r requirements-local.txt
ollama pull gemma3:4b
python -m thud serve
```

Open http://127.0.0.1:8766 and press **Load a demo floor** to try it without a floor. Local TabPFN needs a one-time
licence acceptance at https://ux.priorlabs.ai; set `TABPFN_TOKEN` to your key from there. With only
`requirements.txt` installed, the same token uses the TabPFN API instead.

Gemma 3 4B needs about 4 GB of free memory. On a machine with less, `THUD_GEMMA=gemma3:1b` runs the 1B model
instead: text only, so photos are counted but not described.

Phones only allow the microphone over https. Pass `--host 0.0.0.0 --cert cert.pem --key key.pem` to serve on
your network, or record with the phone's own recorder and upload the file.

Tests: `python -m pytest -rs tests`

## Limits (read these)

- **Not field tested.** Everything is checked on synthetic taps (damped sinusoids, with an extra low mode
  for hollow tiles). No measured set of real hollow tiles has been run yet.
- Until you confirm two solid and two hollow tiles, Thud only ranks tiles by how unusual they sound. A floor
  with no hollow tiles still has a "most unusual" tile.
- Tap detection uses fixed thresholds. Drills, traffic and voices cause extra or missed taps, and one missed tap
  shifts every later tile in that recording. Record row by row and use **Undo last recording**.
- The ledger is tamper-evident, not tamper-proof: publish the head hash somewhere you can't edit. A receipt
  proves what the inspection page sent and when, not that the server recomputed it.
- A crash halfway through writing a receipt leaves a broken last line, and the server won't start until it is
  removed by hand.

## Credits

Photos via Wikimedia Commons: "Cracked tile flooring" by Mk2010 (CC BY-SA 4.0); "FEMA damage inspector in
resident's home in Texas" by Bob McMillan (public domain); "Floor tile installation, LIRR passenger concourse" by
MTA Capital Construction (CC BY 2.0); "US Navy steelworker setting tiles" by U.S. Navy (public domain); "Trowels of
various sizes" by Pittigrilli (CC0). Full sources in `thud/web/assets/credits.json`. Fonts: Anton and Barlow
(SIL OFL).

AI assistance was used for this project: Claude (Anthropic) wrote most of the code and this README under my
direction. I chose the idea, reviewed the results and approved what was published.
