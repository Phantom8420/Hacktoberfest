import argparse
import os
import threading
import webbrowser

from .server import App, run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="effort", description="The most tidiness for the energy you have left.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("EFFORT_PORT", 8780)))
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    if not a.no_browser:
        threading.Timer(0.8, webbrowser.open, [f"http://127.0.0.1:{a.port}"]).start()
    run(App(), a.port)


if __name__ == "__main__":
    main()
