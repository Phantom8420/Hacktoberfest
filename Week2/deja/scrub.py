"""Blank out secrets in OCR'd text before anything touches the disk. A line that
held a secret is also blacked out in the saved screenshot (see capture.py).
"""
import re

MASK = "[hidden]"

TOKENS = [
    r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}",          # OpenAI, Stripe style keys
    r"\bgh[pousr]_[A-Za-z0-9]{20,}", r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",                        # AWS access key id
    r"\bAIza[0-9A-Za-z_-]{30,}",                    # Google API key
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}",              # Slack
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",  # JWT
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]
TOKEN = re.compile("|".join(TOKENS))
# "password: hunter2", "api_key = abc" -> keep the label, hide the value
ASSIGN = re.compile(r"(?i)\b(pass(?:word|wd|code)?|pwd|pin|secret|token|api[ _-]?key|access[ _-]?key|"
                    r"private[ _-]?key|client[ _-]?secret)\b(\s*[:=]\s*)(\S+)")
OTP = re.compile(r"(?i)\b(code|otp|verification|passcode|one[- ]time)\b(\D{0,24}?)(\d{4,8})\b")
CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
# 32+ chars mixing upper, lower and digits: almost always a key. Hex hashes (lowercase) are left alone.
BLOB = re.compile(r"[A-Za-z0-9_\-+/]{32,}")


def _luhn(digits):
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def _card(m):
    digits = re.sub(r"\D", "", m.group())
    return MASK if 13 <= len(digits) <= 19 and _luhn(digits) else m.group()


def _blob(m):
    s = m.group()
    mixed = re.search(r"[a-z]", s) and re.search(r"[A-Z]", s) and re.search(r"\d", s)
    return MASK if mixed else s


def scrub(line):
    """Returns (clean_line, had_secret)."""
    out = TOKEN.sub(MASK, line)
    out = ASSIGN.sub(lambda m: m.group(1) + m.group(2) + MASK, out)
    out = OTP.sub(lambda m: m.group(1) + m.group(2) + MASK, out)
    out = CARD.sub(_card, out)
    out = BLOB.sub(_blob, out)
    return out, out != line
