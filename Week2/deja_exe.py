"""Entry point for Deja.exe, which PyInstaller cannot start as `python -m deja`.

    .venv/Scripts/pyinstaller Deja.spec
"""
import deja.__main__  # noqa: F401  (runs the app)
