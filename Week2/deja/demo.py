"""Sample screens for the hosted demo, where there is no screen to record.

They are dated relative to now, so "yesterday" and "this morning" questions work.
"""
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .capture import save_frame

SCREENS = [  # hours ago, app, window title, background, ink, lines
    (26, "chrome", "Hotel Mirador - Lisbon - Booking", "#ffffff", "#003580",
     ["Hotel Mirador", "Alfama, Lisbon - sea view from every room", "4 nights from 212 per night",
      "Free cancellation until 18 Oct", "Breakfast included - 9.1 Superb"]),
    (25, "chrome", "Casa Lumen - Porto - Booking", "#ffffff", "#0b6e4f",
     ["Casa Lumen", "Ribeira, Porto - river view", "4 nights from 164 per night", "Non-refundable",
      "Rated 8.7 Excellent"]),
    (23, "outlook", "Inbox - Project kickoff", "#f3f6fb", "#1b1b1b",
     ["Project kickoff moved to Thursday 10:30", "Room 4021, bring the Q3 numbers", "From: Priya Shah"]),
    (5, "code", "orders.py - shop - Visual Studio Code", "#1e1e1e", "#d4d4d4",
     ["def fetch_orders(session):", "    return session.get(ORDERS_URL, timeout=30)", "",
      "Traceback (most recent call last):", "ConnectionError: timeout after 30s in fetch_orders()"]),
    (4, "chrome", "Lemon olive oil cake - recipe", "#fffdf8", "#333333",
     ["Lemon olive oil cake", "2 lemons, zested and juiced", "180 C for 45 minutes", "Serves 8"]),
    (3, "chrome", "Trail Runner 4 - running shoes", "#ffffff", "#222222",
     ["Trail Runner 4", "Size 43, colour slate", "89.00 with code AUTUMN15", "Free returns for 30 days"]),
    (2, "slack", "design-team - Slack", "#ffffff", "#1d1c1d",
     ["Lena: the new logo files are in Drive > Brand > 2026", "Omar: launch review is Friday at 3",
      "Lena: use the blue from the style guide, 1F5FBF"]),
    (1, "chrome", "Flight LIS to AMS - check-in", "#ffffff", "#0a3d62",
     ["Check-in is open", "Flight TP 662, Lisbon to Amsterdam", "Departs 07:45 from gate 14",
      "Booking reference QX7KD2"]),
]


def _render(title, bg, ink, lines):
    im = Image.new("RGB", (1600, 1000), bg)
    d = ImageDraw.Draw(im)
    dark = bg == "#1e1e1e"
    d.rectangle([0, 0, 1600, 56], fill="#323233" if dark else "#dfe3e8")
    d.text((24, 14), title, fill="#cccccc" if dark else "#222222", font=ImageFont.load_default(24))
    d.text((80, 130), lines[0], fill=ink, font=ImageFont.load_default(58))
    for i, line in enumerate(lines[1:]):
        d.text((80, 240 + i * 64), line, fill=ink if dark else "#333333", font=ImageFont.load_default(36))
    return np.asarray(im)[:, :, ::-1].copy()


def seed(store):
    """Fill an empty store with the sample day. Returns how many screens were added."""
    if store.stats()["frames"]:
        return 0
    now = time.time()
    for hours, app, title, bg, ink, lines in SCREENS:
        t = now - hours * 3600
        rel = save_frame(_render(title, bg, ink, lines), store.home, t, [], [])
        store.add_frame(t, app, title, rel, "\n".join(lines))
    store.add_note("Call the dentist", "reminder", now + 86400)
    store.add_note("Renew the passport", "todo")
    store.add_note("The spare key is with Sam", "note")
    return len(SCREENS)
