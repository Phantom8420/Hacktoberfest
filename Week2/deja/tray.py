"""A tray icon, so Déjà can live in the background from sign-in: click to open,
right-click to pause, forget the last 5 minutes, or quit. Also the Startup shortcut.
"""
import os
import sys
import webbrowser
from pathlib import Path

import win32api
import win32con
import win32gui
from PIL import Image, ImageDraw

WM_TRAY = win32con.WM_USER + 20
STARTUP = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/Deja.lnk"


def _icon(path):
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([2, 2, 61, 61], 16, fill="#111827")
    d.ellipse([12, 19, 51, 44], outline="#2F7CF6", width=6)
    im.save(path, sizes=[(16, 16), (32, 32), (64, 64)])
    return win32gui.LoadImage(0, str(path), win32con.IMAGE_ICON, 0, 0,
                              win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)


def run(url, app, icon_path):
    """Blocks in the Windows message loop; call it on its own thread."""
    def tip(hwnd):
        state = "paused" if app.settings.paused else "recording"
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (hwnd, 0, win32gui.NIF_TIP, WM_TRAY, hicon, f"Déjà, {state}"))

    def menu(hwnd):
        items = [("Open Déjà", lambda: webbrowser.open(url)),
                 ("Resume" if app.settings.paused else "Pause", app.toggle_pause),
                 ("Forget the last 5 minutes", app.forget_recent),
                 ("Start at sign-in", lambda: uninstall() if STARTUP.exists() else install()),
                 ("Quit", lambda: os._exit(0))]
        m = win32gui.CreatePopupMenu()
        for i, (label, _) in enumerate(items, 1):
            checked = label == "Start at sign-in" and STARTUP.exists()
            win32gui.AppendMenu(m, win32con.MF_STRING | (win32con.MF_CHECKED if checked else 0), i, label)
        win32gui.SetForegroundWindow(hwnd)  # without this the menu never closes on an outside click
        pick = win32gui.TrackPopupMenu(m, win32con.TPM_RIGHTBUTTON | win32con.TPM_RETURNCMD,
                                       *win32gui.GetCursorPos(), 0, hwnd, None)
        win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
        if pick:
            items[pick - 1][1]()
            tip(hwnd)

    def proc(hwnd, msg, wp, lp):
        if msg == WM_TRAY:
            if lp == win32con.WM_LBUTTONUP:
                webbrowser.open(url)
            elif lp == win32con.WM_RBUTTONUP:
                menu(hwnd)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wp, lp)

    wc = win32gui.WNDCLASS()
    wc.hInstance, wc.lpszClassName, wc.lpfnWndProc = win32api.GetModuleHandle(None), "DejaTray", proc
    win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow("DejaTray", "Déjà", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
    hicon = _icon(icon_path)
    win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, (hwnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                                                 WM_TRAY, hicon, "Déjà"))
    tip(hwnd)
    win32gui.PumpMessages()


def install():
    """Start Déjà quietly at every sign-in, so reminders fire even if the page was never opened."""
    import win32com.client
    STARTUP.parent.mkdir(parents=True, exist_ok=True)
    link = win32com.client.Dispatch("WScript.Shell").CreateShortCut(str(STARTUP))
    if getattr(sys, "frozen", False):  # Deja.exe
        link.TargetPath, link.Arguments = sys.executable, "--no-browser"
        link.WorkingDirectory = str(Path(sys.executable).parent)
    else:
        link.TargetPath = str(Path(sys.executable).with_name("pythonw.exe"))
        link.Arguments = "-m deja --no-browser"
        link.WorkingDirectory = str(Path(__file__).parent.parent)
    link.Description = "Déjà, a memory of your screen"
    link.save()
    return STARTUP


def uninstall():
    STARTUP.unlink(missing_ok=True)
    return STARTUP
