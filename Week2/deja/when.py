"""Plain-language times, parsed by code (a 1B model gets "last Tuesday" wrong).
past(): "what was that hotel last tuesday" -> a time window to search.
due():  "remind me to call mum tomorrow at 5" -> when to remind.
"""
import re
from datetime import datetime, timedelta

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PARTS = {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 24), "night": (18, 28)}
UNITS = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800}
WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "few": 3, "couple": 2}


def _day(d):
    return datetime(d.year, d.month, d.day)


def _num(s):
    return int(s) if s.isdigit() else WORDS.get(s, 1)


def _cut(text, m):
    return re.sub(r"\s{2,}", " ", (text[:m.start()] + " " + text[m.end():])).strip()


def _window(day, part):
    lo, hi = PARTS[part] if part else (0, 24)
    return day + timedelta(hours=lo), day + timedelta(hours=hi)


def past(text, now=None):
    """Returns (start, end, rest_of_text); start/end are datetimes or None."""
    now = now or datetime.now()
    today = _day(now)
    t = text.lower()

    m = re.search(r"\b(\d+|an?|one|two|three|four|five|ten|few|couple)(?: of)? (minute|hour|day|week)s? ago\b", t)
    if m:
        n, unit = _num(m.group(1)), UNITS[m.group(2)]
        if m.group(2) in ("day", "week"):
            start = today - timedelta(seconds=n * unit)
            return start, start + timedelta(seconds=unit), _cut(text, m)
        at = now - timedelta(seconds=n * unit)
        return at - timedelta(seconds=unit), at + timedelta(seconds=unit), _cut(text, m)

    m = re.search(r"\blast night\b", t)
    if m:
        return _window(today - timedelta(days=1), "night") + (_cut(text, m),)
    m = re.search(r"\b(today|yesterday)(?: (morning|afternoon|evening))?\b|\bthis (morning|afternoon|evening)\b", t)
    if m:
        day = today - timedelta(days=1) if m.group(1) == "yesterday" else today
        return _window(day, m.group(2) or m.group(3)) + (_cut(text, m),)
    m = re.search(r"\btonight\b|\bearlier\b", t)
    if m:
        return today, now, _cut(text, m)

    m = re.search(r"\b(?:(last|this past|on|this) )?(" + "|".join(DAYS) + r")(?: (morning|afternoon|evening|night))?\b", t)
    if m:
        back = (now.weekday() - DAYS.index(m.group(2))) % 7
        if back == 0 and m.group(1) in ("last", "this past"):
            back = 7
        return _window(today - timedelta(days=back), m.group(3)) + (_cut(text, m),)

    m = re.search(r"\b(last|this) week\b", t)
    if m:
        monday = today - timedelta(days=now.weekday())
        if m.group(1) == "this":
            return monday, now, _cut(text, m)
        return monday - timedelta(days=7), monday, _cut(text, m)
    return None, None, text


def due(text, now=None):
    """Returns (datetime or None, rest_of_text)."""
    now = now or datetime.now()
    today = _day(now)
    t = text.lower()

    m = re.search(r"\bin (\d+|an?|one|two|three|four|five|ten|few|couple)(?: of)? (minute|hour|day|week)s?\b", t)
    if m:
        return now + timedelta(seconds=_num(m.group(1)) * UNITS[m.group(2)]), _cut(text, m)

    day, hour, rest = None, None, text
    m = re.search(r"\b(tomorrow|tonight|this (?:morning|afternoon|evening)|next week|"
                  r"(?:on |next |this )?(?:" + "|".join(DAYS) + r"))\b", t)
    if m:
        w = m.group(1)
        if w == "tomorrow":
            day, hour = today + timedelta(days=1), 9
        elif w == "tonight":
            day, hour = today, 20
        elif w.startswith("this ") and w.split()[1] in PARTS:
            day, hour = today, {"morning": 9, "afternoon": 15, "evening": 18}[w.split()[1]]
        elif w == "next week":
            day, hour = today + timedelta(days=7 - now.weekday()), 9
        else:
            ahead = (DAYS.index(w.split()[-1]) - now.weekday()) % 7 or 7
            day, hour = today + timedelta(days=ahead), 9
        rest = _cut(rest, re.search(re.escape(m.group(0)), rest, re.I))

    m = re.search(r"\b(?:at|by) (\d{1,2})(?:[:.](\d{2}))? ?(am|pm|a\.m\.|p\.m\.)?\b", rest.lower())
    if m:
        h, mins = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").replace(".", "")
        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        elif not ampm and h < 8:
            h += 12  # "at 5" means 5 pm
        if h > 23 or mins > 59:
            return (day + timedelta(hours=hour) if day else None), rest
        rest = _cut(rest, m)
        if day is None:
            day = today if now < today + timedelta(hours=h, minutes=mins) else today + timedelta(days=1)
        return day + timedelta(hours=h, minutes=mins), rest
    return (day + timedelta(hours=hour) if day else None), rest
