"""Screen capture -> OCR -> scrub -> store, on two background threads.

What never gets recorded:
- windows that ask Windows not to be captured (password managers, DRM video) come
  out black on their own, the same way they do in any screen recorder;
- the lock screen and admin prompts (they live on a separate secure desktop);
- private browser windows and any app on the excluded list;
- anything while paused.
"""
import ctypes
import io
import json
import os
import queue
import re
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .scrub import scrub

PRIVATE = re.compile(r"InPrivate|Incognito|Private Browsing|Private window|\(Private\)", re.I)
DEFAULT_EXCLUDED = ["1password.exe", "bitwarden.exe", "keepass.exe", "keepassxc.exe", "dashlane.exe",
                    "lastpass.exe", "credentialuibroker.exe", "consent.exe", "logonui.exe", "lockapp.exe"]


class Settings:
    def __init__(self, path):
        self.path = Path(path)
        self.excluded, self.interval, self.keep_days, self.paused = list(DEFAULT_EXCLUDED), 5, 30, False
        if self.path.exists():
            for k, v in json.loads(self.path.read_text("utf8")).items():
                if k in ("excluded", "interval", "keep_days", "paused"):
                    setattr(self, k, v)

    def dict(self):
        return {"excluded": self.excluded, "interval": self.interval, "keep_days": self.keep_days, "paused": self.paused}

    def update(self, d):
        if "excluded" in d:
            self.excluded = sorted({str(x).strip().lower() for x in d["excluded"] if str(x).strip()})
        if "interval" in d:
            self.interval = min(60, max(2, int(d["interval"])))
        if "keep_days" in d:
            self.keep_days = min(365, max(1, int(d["keep_days"])))
        if "paused" in d:
            self.paused = bool(d["paused"])
        self.path.write_text(json.dumps(self.dict(), indent=1), "utf8")


def locked():
    """True on the lock screen, UAC prompts and other secure desktops."""
    u = ctypes.windll.user32
    h = u.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not h:
        return True
    ok = u.SwitchDesktop(h)
    u.CloseDesktop(h)
    return not ok


def foreground():
    """(hwnd, exe name, window title) of the window in front."""
    import psutil
    import win32gui
    import win32process
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return 0, "", ""
    try:
        exe = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1]).name().lower()
    except Exception:
        exe = ""
    return hwnd, exe, win32gui.GetWindowText(hwnd)


def monitor_rect(hwnd):
    import win32api
    l, t, r, b = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd, 2))["Monitor"]
    return {"left": l, "top": t, "width": r - l, "height": b - t}


def thumb(bgr):
    return np.asarray(Image.fromarray(bgr[:, :, ::-1]).convert("L").resize((64, 40)), dtype=np.int16)


def save_frame(bgr, store, t, boxes, secret_lines):
    """Encrypted JPEG at most 1600 px wide, with every line that held a secret painted over."""
    im = Image.fromarray(np.ascontiguousarray(bgr[:, :, ::-1]))
    draw = ImageDraw.Draw(im)
    for i in secret_lines:  # whole padded rectangle: OCR boxes are slanted and can clip a glyph's edge
        pts = np.asarray(boxes[i])
        draw.rectangle([*(pts.min(0) - 4).tolist(), *(pts.max(0) + 4).tolist()], fill="black")
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    stamp = time.localtime(t)
    rel = f"{time.strftime('%Y-%m-%d', stamp)}/{time.strftime('%H%M%S', stamp)}_{int(t * 1000) % 1000:03d}.jpg"
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    store.put_image(rel, buf.getvalue())
    return rel


def read(engine, bgr):
    """OCR -> (scrubbed text, boxes, indexes of lines that held a secret)."""
    r = engine(bgr)
    lines, secret = [], []
    for i, txt in enumerate(r.txts or ()):
        clean, hit = scrub(txt)
        lines.append(clean)
        if hit:
            secret.append(i)
    return "\n".join(lines), (r.boxes if r.boxes is not None else []), secret


def ocr_engine():
    from rapidocr import RapidOCR
    return RapidOCR(params={"Global.log_level": "error", "Global.use_cls": False,
                            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                            "EngineConfig.onnxruntime.inter_op_num_threads": 1})


class Recorder:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.state, self.last = "starting", None  # state is shown on the page
        self.ocr_error = None  # kept apart so the grab loop can't paper over it
        self.backlog = queue.Queue(maxsize=1)
        self._last_thumb, self._last_title, self._pruned = None, None, 0

    def start(self):
        threading.Thread(target=self._grab_loop, daemon=True, name="grab").start()
        threading.Thread(target=self._ocr_loop, daemon=True, name="ocr").start()

    def skip_reason(self, exe, title):
        if self.settings.paused:
            return "paused"
        if locked():
            return "locked"
        if exe in self.settings.excluded:
            return f"skipping {exe}"
        if PRIVATE.search(title):
            return "skipping a private window"
        return None

    def grab_once(self):
        import mss
        hwnd, exe, title = foreground()
        reason = self.skip_reason(exe, title)
        if reason or not hwnd:
            self.state = reason or "idle"
            return None
        with mss.MSS() as s:
            bgr = np.asarray(s.grab(monitor_rect(hwnd)))[:, :, :3]
        if bgr.mean() < 2:  # a black frame: protected window or screen off
            self.state = "screen hidden"
            return None
        th = thumb(bgr)
        changed = (self._last_thumb is None or title != self._last_title
                   or np.abs(th - self._last_thumb).mean() > 3)
        self.state = self.ocr_error or "recording"
        if not changed:
            return None
        self._last_thumb, self._last_title = th, title
        return time.time(), exe, title, bgr

    def _grab_loop(self):
        while True:
            try:
                item = self.grab_once()
                if item:
                    try:
                        self.backlog.put_nowait(item)
                    except queue.Full:  # OCR is behind: keep only the newest frame
                        try:
                            self.backlog.get_nowait()
                        except queue.Empty:
                            pass
                        self.backlog.put_nowait(item)
                if time.time() - self._pruned > 3600:
                    self.store.forget(before=time.time() - self.settings.keep_days * 86400)
                    self._pruned = time.time()
            except Exception as e:
                self.state = f"error: {e}"
            time.sleep(self.settings.interval)

    def _ocr_loop(self):
        try:
            engine = ocr_engine()
        except Exception as e:  # usually too little free memory to load the models
            self.state = self.ocr_error = f"error: can't start reading the screen ({e})"
            return
        while True:
            t, exe, title, bgr = self.backlog.get()
            try:
                if self.settings.paused:
                    continue  # paused while this frame waited
                text, boxes, secret = read(engine, bgr)
                rel = save_frame(bgr, self.store, t, boxes, secret)
                self.store.add_frame(t, exe.removesuffix(".exe"), scrub(title)[0], rel, text)
                self.last, self.ocr_error = t, None
            except Exception as e:
                self.state = self.ocr_error = f"error: {e}"


def lower_priority():
    """OCR is heavy; the user's own work must always win the CPU."""
    import psutil
    try:
        psutil.Process(os.getpid()).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
