# Déjà

A memory of your own screen that you can talk to. Windows, fully local. [Try the demo](https://deja-mu.vercel.app) (sample screens).

Every few seconds Déjà reads what is on your screen, keeps the text in a search index on your disk next to a small
screenshot, and lets you ask about it later, by voice or by typing:

- "What was that hotel I looked at yesterday?"
- "What error did I get in orders.py this morning?"
- "Remind me to call the dentist tomorrow at 5"
- "Note that the spare key is with Sam"

Questions come back as one sentence plus the screenshots that matched, with the one the answer came from circled.
Reminders pop up as a Windows notification when they are due.

## Run it

Needs Windows 10/11 and Python 3.11 or newer. [Ollama](https://ollama.com) with `gemma3:1b` is optional: without it
you still get the matching screenshots, just no one-line answer.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
ollama pull gemma3:1b
.venv/Scripts/python -m deja
```

It opens `http://127.0.0.1:8777` in your browser and starts recording. The first spoken question downloads the Whisper
`base.en` model (about 140 MB) and the OCR models once.

| option | what it does |
|---|---|
| `--home DIR` | where memories are kept (default `%LOCALAPPDATA%\Deja`) |
| `--port N` | web page port (default 8777) |
| `--no-record` | open the app without recording |
| `--no-browser` | don't open the page |
| `--public` | serve the sample screens to other machines, read-only, no recording |

Hotkeys, anywhere in Windows: **Ctrl Alt P** pauses or resumes, **Ctrl Alt F** forgets the last 5 minutes.

## Online demo

A web page can't see your screen, so the online demo is a static site in `site/` with a day of sample screens
(`deja/demo.py`). `build_site.py` runs the real search and Gemma on a set of questions once and saves the
answers; in the browser, `deja/web/static.js` stands in for the local server, replays those answers and searches
the sample screens itself for anything else. Notes and reminders are parsed but not kept, and there is no mic.

```bash
.venv/Scripts/python build_site.py   # needs Ollama with gemma3:1b running
cd site && npx vercel deploy --prod   # live at https://deja-mu.vercel.app
```

Any static host works: it is plain files, no build step. On Vercel's dashboard, import the repo and set the
root directory to `Week2/site`.

## What it never records

- **Windows that ask not to be captured.** Password managers, banking apps and DRM video that set Windows' capture
  exclusion come out black, the same way they do in any screen recorder. Black frames are thrown away.
- **The lock screen, sign-in and admin (UAC) prompts.** They live on a separate secure desktop; Déjà checks for it
  and skips.
- **Private browser windows** (InPrivate, Incognito, Private Browsing) and any app on the excluded list (password
  managers are on it by default; edit it in Settings).
- **Anything while paused.**

Before a screen is saved, every line that looks like a secret is replaced in the text and painted black in the
screenshot: API keys and tokens, `password = ...` lines, card numbers that pass the Luhn check, one-time codes, and
long random-looking strings.

Nothing leaves the computer. The web page listens on 127.0.0.1 only and refuses requests from other websites (it
checks the Host header and the browser's Sec-Fetch-Site, and only accepts JSON or audio bodies). Screens older than
30 days are deleted (change it in Settings). You can forget one screen, the last 5 minutes, or everything.

## How it works

| step | done by |
|---|---|
| capture the foreground window's monitor when it changes | `mss`, a 64×40 thumbnail diff |
| read the text | RapidOCR (PP-OCR, ONNX Runtime, CPU) |
| hide secrets | regular expressions in `deja/scrub.py` |
| store and search | SQLite FTS5 with a trigram index, so "error" finds "ConnectionError" |
| hear you | faster-whisper `base.en`, int8 on CPU |
| note or question, and when | code: `deja/voice.py` and `deja/when.py` ("tomorrow at 5", "last tuesday", "in 20 minutes") |
| answer | Gemma 3 1B through Ollama, given only the top five matching screens |

The model never searches. Code finds the screens, Gemma only reads the few that matched and says which one answers
you. If its answer contains a number that was not on any of those screens, the answer is dropped and you see the
screenshots instead.

Measured on an i5-12500H laptop with no GPU: OCR takes about 5 s for a full 2880×1800 screen (it runs at below-normal
priority, and when it falls behind it skips to the newest screen); Whisper turns a short spoken question into text in
under a second.

## Limits

- Windows only (capture, secure-desktop check, hotkeys, notifications).
- Text, not pictures: it finds what was written on screen, not what an image showed.
- A 1B model sometimes gives a clumsy or partial sentence. The screenshots underneath are always the real evidence.
- The secret filter is pattern-based. It will miss a password typed somewhere that does not look like one, so keep
  password managers excluded and pause for anything sensitive.
- Times are read in English only.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

22 tests: secret scrubbing (both directions), time parsing, note/question routing, search and forgetting, the
number check on answers, OCR painting a key black in a real screenshot, the server refusing other sites, the
read-only hosted demo, and Whisper hearing a spoken reminder.

## Credits

RapidOCR and PaddleOCR (Apache-2.0), faster-whisper (MIT) and OpenAI Whisper (MIT), Gemma 3 (Gemma Terms of Use),
Ollama (MIT), python-mss (MIT).

AI assistance was used for this project: Claude (Anthropic) wrote most of the code and this README under my
direction.
