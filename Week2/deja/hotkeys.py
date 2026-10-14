"""Ctrl+Alt+P pauses or resumes; Ctrl+Alt+F forgets the last five minutes.
They work from any app, so you never have to open Déjà to stop it.
"""
import ctypes
import ctypes.wintypes
import threading

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x0312


def listen(actions):
    """actions: {"P": callback, "F": callback}. Returns the keys that registered."""
    ready, ok = threading.Event(), []

    def loop():
        u = ctypes.windll.user32
        ids = {}
        for i, key in enumerate(actions, 1):
            if u.RegisterHotKey(None, i, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(key)):
                ids[i] = actions[key]
                ok.append(key)  # another app may already own the combination
        ready.set()
        msg = ctypes.wintypes.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in ids:
                try:
                    ids[msg.wParam]()
                except Exception:
                    pass

    threading.Thread(target=loop, daemon=True, name="hotkeys").start()
    ready.wait(2)
    return ok
