"""Talking to Gemma, local through Ollama, and getting photos ready for it.

Every photo goes through clean() first: phone pictures carry GPS in their EXIF, and
a picture of your room shouldn't say where your room is.
"""
import base64
import io
import json
import os
import urllib.request

from PIL import Image, ImageOps

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("EFFORT_GEMMA", "gemma3:4b")
SIDE = 1024  # longest side sent to the model; much faster on a CPU, barely changes what it sees


def clean(data, side=SIDE):
    """JPEG bytes with no EXIF (no GPS, no camera serial), upright, at most `side` px."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((side, side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)  # a fresh save without exif= writes none
    return out.getvalue()


def chat(prompt, images=(), schema=None, timeout=300):
    """One reply from Gemma. images are cleaned JPEG bytes; with a schema the reply is parsed JSON."""
    msg = {"role": "user", "content": prompt, "images": [base64.b64encode(i).decode() for i in images]}
    body = {"model": MODEL, "stream": False, "keep_alive": "10m", "options": {"temperature": 0, "use_mmap": True},  # mmap: weights don't eat commit memory
            "messages": [msg]}
    if schema:
        body["format"] = schema
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = json.loads(r.read())["message"]["content"].strip()
    return json.loads(text) if schema else text
