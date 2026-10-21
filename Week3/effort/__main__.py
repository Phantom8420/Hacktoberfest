import argparse
import json
import os
import secrets
import socket
import threading
import urllib.request
import webbrowser

from . import gemma
from .server import App, run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="effort", description="The most tidiness for the energy you have left.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("EFFORT_PORT", 8780)))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--phone", action="store_true", help="also listen on the home network, for taking the photo with a phone")
    a = ap.parse_args(argv)
    if problem := check_ollama():
        print(problem, flush=True)
    if not a.no_browser:
        threading.Timer(0.8, webbrowser.open, [f"http://127.0.0.1:{a.port}"]).start()
    run(App(), a.port, *((lan_ip(), secrets.token_urlsafe(12)) if a.phone else ()))


def lan_ip():
    """This computer's address on the home network (a UDP "connect" sends nothing)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.168.0.1", 9))
        return s.getsockname()[0]


def check_ollama():
    """What to fix before a photo can work, or None. Said now, not two minutes into the first photo."""
    try:
        with urllib.request.urlopen(f"{gemma.OLLAMA}/api/tags", timeout=3) as r:
            names = {m["name"] for m in json.load(r)["models"]}
    except OSError:
        return f"Ollama isn't answering at {gemma.OLLAMA}. Start it (open the Ollama app, or run `ollama serve`)."
    if gemma.MODEL not in names and f"{gemma.MODEL}:latest" not in names:
        return f"Ollama doesn't have {gemma.MODEL} yet. Run: ollama pull {gemma.MODEL}"
    return None


if __name__ == "__main__":
    main()
