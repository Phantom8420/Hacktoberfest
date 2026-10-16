import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path


def load_env(path=".env"):
    """KEY=value lines; real environment variables win."""
    if os.path.exists(path):
        for line in open(path, encoding="utf8"):
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip())


def main(argv=None):
    load_env()
    home = os.environ.get("DEJA_HOME") or str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Deja")
    ap = argparse.ArgumentParser(prog="deja", description="A memory of your screen that you can talk to.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DEJA_PORT", 8777)))
    ap.add_argument("--home", default=home, help=f"where memories are kept (default {home})")
    ap.add_argument("--no-record", action="store_true", help="open the app without recording the screen")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--public", action="store_true", default=bool(os.environ.get("DEJA_PUBLIC")),
                    help="hosted demo: sample screens, no recording, read-only, listens on all interfaces")
    ap.add_argument("--install", action="store_true", help="start Déjà at every sign-in, in the tray")
    ap.add_argument("--uninstall", action="store_true", help="stop starting Déjà at sign-in")
    a = ap.parse_args(argv)
    if a.install or a.uninstall:
        from . import tray
        print(("Added " if a.install else "Removed ") + str(tray.install() if a.install else tray.uninstall()))
        return

    from .capture import Recorder, Settings, lower_priority
    from .server import App, run
    from .store import Store

    store = Store(a.home)
    settings = Settings(Path(a.home) / "settings.json")
    if a.public:
        from .demo import seed
        seed(store)
        return run(App(store, settings, public=True), a.port, "0.0.0.0")
    recorder = None
    if not a.no_record:
        lower_priority()
        recorder = Recorder(store, settings)
        recorder.start()
    from .hotkeys import listen  # Windows only
    app = App(store, settings, recorder)
    app.hotkeys = listen({"P": app.toggle_pause, "F": app.forget_recent})
    url = f"http://127.0.0.1:{a.port}"
    from . import tray
    threading.Thread(target=tray.run, args=(url, app, Path(a.home) / "deja.ico"), daemon=True, name="tray").start()
    if not a.no_browser:
        webbrowser.open(url)
    run(app, a.port)


sys.exit(main())
