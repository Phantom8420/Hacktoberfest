"""How well does Déjà read a screen? Renders 20 synthetic screens with known text and runs them
through the same OCR the recorder uses: 14 ordinary ones (Windows fonts at 12-20px, light and dark
themes, code) and 6 deliberately hard ones (10-11px, low contrast, text over a busy picture).
Rendered text is cleaner than a real screen, so read the result as a best case.

    python ocr_eval.py
"""
import re
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from deja import capture

LINES = [
    "Hotel Mirador - 4 nights from 212 per night, free cancellation until Oct 20",
    "ConnectionError: timeout after 30s in fetch_orders()",
    "Re: Quarterly planning - can we move the review to Thursday at 3pm?",
    "Gate 14 closes 25 minutes before departure. Seat 22A, boarding group 3",
    "def total(items): return sum(i.price * i.qty for i in items)",
    "Your order #48213 has shipped and should arrive on Monday",
    "Lemon risotto: 300g arborio rice, 1 litre stock, 2 lemons, parmesan",
    "git commit -m \"Fix rounding in invoice totals\"",
    "Meeting notes: Sam owns the migration, Priya reviews the API changes",
    "Battery 64% - about 3 hr 10 min remaining",
]
THEMES = [("white", "black"), ("#1e1e1e", "#d4d4d4"), ("#f3f3f3", "#333333"), ("#0d1117", "#c9d1d9")]
FONTS = [("segoeui.ttf", 15), ("consola.ttf", 14), ("arial.ttf", 13), ("calibri.ttf", 15), ("tahoma.ttf", 12),
         ("segoeui.ttf", 12), ("consola.ttf", 12), ("verdana.ttf", 12), ("times.ttf", 16), ("segoeui.ttf", 20)]


HARD = [("segoeui.ttf", 10, "white", "#555555", "10px"), ("tahoma.ttf", 11, "#1e1e1e", "#9a9a9a", "11px"),
        ("segoeui.ttf", 14, "#b8b8b8", "#7a7a7a", "low contrast"), ("arial.ttf", 13, "#30343c", "#6c7480", "low contrast"),
        ("segoeui.ttf", 15, None, "white", "over a busy picture"), ("consola.ttf", 11, None, "#e8e8e8", "11px over a picture")]


def screen(i):
    if i < 14:
        font_file, size = FONTS[i % len(FONTS)]
        bg, fg = THEMES[i % len(THEMES)]
        label = f"{font_file[:-4]} {size}px on {bg}"
    else:
        font_file, size, bg, fg, why = HARD[i - 14]
        label = f"{font_file[:-4]} {size}px, {why}"
    font = ImageFont.truetype(font_file, size)
    lines = [LINES[(i + k) % len(LINES)] for k in range(4)]
    h = 60 + 40 * len(lines)
    if bg:
        im = Image.new("RGB", (1280, h), bg)
    else:  # smooth colour blobs plus grain, like a photo behind a caption
        rng = np.random.default_rng(i)
        blobs = np.kron(rng.integers(30, 200, (h // 40 + 1, 1280 // 40, 3)), np.ones((40, 40, 1)))[:h]
        im = Image.fromarray(np.clip(blobs + rng.normal(0, 18, blobs.shape), 0, 255).astype("uint8"))
    d = ImageDraw.Draw(im)
    for k, line in enumerate(lines):
        d.text((30, 30 + 40 * k), line, fill=fg, font=font)
    return np.asarray(im)[:, :, ::-1].copy(), lines, label


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def main():
    engine = capture.ocr_engine()
    totals = {"ordinary": [0, 0, 0, 0], "hard": [0, 0, 0, 0]}  # chars, errors, words, words found
    for i in range(20):
        bgr, lines, label = screen(i)
        text, _, _ = capture.read(engine, bgr)
        truth, got = norm(" ".join(lines)), norm(text)
        e = distance(truth, got)
        want, have = Counter(truth.lower().split()), Counter(got.lower().split())
        hit, n = sum((want & have).values()), sum(want.values())
        t = totals["ordinary" if i < 14 else "hard"]
        t[:] = t[0] + len(truth), t[1] + e, t[2] + n, t[3] + hit
        print(f"{i + 1:2}. {label:34} chars {1 - e / len(truth):6.1%}  words {hit / n:6.1%}")
    print()
    for name, (chars, errs, words, found) in totals.items():
        print(f"{name}: characters right {1 - errs / chars:.1%}, words read exactly {found / words:.1%}")

assert distance("kitten", "sitting") == 3
if __name__ == "__main__":
    main()
