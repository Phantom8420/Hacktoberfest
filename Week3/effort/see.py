"""Photo of a room -> the things worth moving, each with a guess at effort and payoff.

Gemma only looks; the numbers it gives are clamped and the destinations forced into a
fixed list, because learn.py calibrates effort per destination.
"""
import re

from . import gemma

PLACES = ["bin", "laundry", "wardrobe", "shelf", "drawer", "sink", "desk-side", "other"]
MAX_ITEMS = 20

SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object", "required": ["what", "zone", "move_to", "est_seconds", "mess"],
    "properties": {"what": {"type": "string"}, "zone": {"type": "string"},
                   "move_to": {"type": "string", "enum": PLACES},
                   "est_seconds": {"type": "integer"}, "mess": {"type": "integer"}}}}}}

PROMPT = f"""You are helping a very tired person tidy this room with the least effort.
List the loose things in the photo that make the room look messy and that one person could put away.

Rules:
- Only objects you can clearly see. Never guess at hidden ones.
- Furniture, appliances and things already where they belong are not items.
- A heap of the same kind of thing is one item, e.g. "pile of shirts on bed".
- what: 2 to 5 plain words. zone: the surface or area it is on, 1 or 2 words (floor, bed, desk, chair...).
- move_to: one of {", ".join(PLACES)}.
- est_seconds: how long putting it away takes, picking up to done, 2 to 300.
- mess: 1 to 5, how much tidier the room looks once it is gone (5 = the room looks much better).
At most {MAX_ITEMS} items, the messiest first."""


# Gemma lists these despite the prompt; nobody "puts away" a wall heater or a desk
FIXTURES = {"wall", "ceiling", "window", "curtain", "blind", "door", "light", "lamp", "fan", "heater", "radiator",
            "outlet", "socket", "switch", "frame", "picture", "poster", "mirror", "clock", "tv", "television",
            "monitor", "computer", "laptop", "printer", "desk", "table", "chair", "bed", "sofa", "couch", "shelf",
            "shelve", "bookcase", "wardrobe", "closet", "dresser", "cabinet", "drawer", "rug", "carpet", "mattress",
            "pillow", "cushion"}


def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())[:40]


def fixture(what, zone, move_to):
    """True for things that aren't loose mess: furniture, fixtures, and things already where they go."""
    if zone in ("wall", "ceiling", "window") or zone == move_to:
        return True
    head = re.split(r" (?:on|in|under|by|near|against|next to) ", what)[0]  # "pile of books on desk" -> "pile of books"
    head = head.split(" of ", 1)[-1]                                       # -> "books"
    return any(w.rstrip("s") in FIXTURES for w in head.split())


def tidy(raw):
    """Clamp, dedupe and drop fixtures from whatever the model returned; give each item an id."""
    out, seen = [], set()
    for it in raw.get("items", []) if isinstance(raw, dict) else []:
        if not isinstance(it, dict):
            continue
        what, zone = _norm(it.get("what", "")), _norm(it.get("zone", "")) or "room"
        place = _norm(it.get("move_to", ""))
        if not what or (what, zone) in seen or fixture(what, zone, place):
            continue
        seen.add((what, zone))
        try:
            secs, mess = int(it.get("est_seconds", 30)), int(it.get("mess", 2))
        except (TypeError, ValueError):
            secs, mess = 30, 2
        out.append({"id": len(out) + 1, "what": what, "zone": zone,
                    "move_to": place if place in PLACES else "other",
                    "est_seconds": min(300, max(2, secs)), "mess": min(5, max(1, mess))})
        if len(out) == MAX_ITEMS:
            break
    return out


def look(photo):
    """Cleaned JPEG bytes -> list of items. One retry if the JSON comes back broken."""
    for attempt in (1, 2):
        try:
            return tidy(gemma.chat(PROMPT, [photo], schema=SCHEMA))
        except ValueError:
            if attempt == 2:
                raise
