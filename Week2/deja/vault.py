"""Everything Déjà writes to disk is encrypted (AES-256-GCM) with a key that only your
Windows account can unlock (DPAPI). Copy the folder to another account or PC and it is noise.

Search runs on keyed hashes of each three-letter piece of text, kept in order, so the
index can still find "error" inside "ConnectionError" but holds no readable text.
"""
import hashlib
import secrets
from pathlib import Path

import win32crypt
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

UI_FORBIDDEN = 0x1  # fail instead of popping a dialog: this runs in the background


class Vault:
    def __init__(self, keyfile):
        p = Path(keyfile)
        if p.exists():
            key = win32crypt.CryptUnprotectData(p.read_bytes(), None, None, None, UI_FORBIDDEN)[1]
        else:
            key = secrets.token_bytes(32)
            p.write_bytes(win32crypt.CryptProtectData(key, "Deja", None, None, None, UI_FORBIDDEN))
        self._aes = AESGCM(hashlib.sha256(key + b"enc").digest())
        self._idx = hashlib.sha256(key + b"idx").digest()

    def seal(self, data):
        nonce = secrets.token_bytes(12)
        return nonce + self._aes.encrypt(nonce, data, None)

    def open(self, blob):
        try:
            return self._aes.decrypt(blob[:12], blob[12:], None)
        except InvalidTag:
            raise ValueError("this file was changed or belongs to another Windows account") from None

    def seal_text(self, s):
        return None if s is None else self.seal(s.encode())

    def open_text(self, blob):
        return None if blob is None else self.open(blob).decode()

    def tokens(self, text):
        """One keyed hash per three-letter piece, in order: a phrase query of them is a substring match."""
        s = (text or "").lower()
        return " ".join(hashlib.blake2b(s[i:i + 3].encode(), digest_size=6, key=self._idx).hexdigest()
                        for i in range(len(s) - 2))
