"""Everything Déjà writes to disk is encrypted with a key that only your Windows
account can unlock (DPAPI). Copy the folder to another account or PC and it is noise.

Search runs on keyed hashes of each three-letter piece of text, kept in order, so the
index can still find "error" inside "ConnectionError" but holds no readable text.
"""
import hashlib
import hmac
import secrets
from pathlib import Path

import win32crypt

UI_FORBIDDEN = 0x1  # fail instead of popping a dialog: this runs in the background


def _xor(data, pad):
    return (int.from_bytes(data, "little") ^ int.from_bytes(pad, "little")).to_bytes(len(data), "little")


class Vault:
    def __init__(self, keyfile):
        p = Path(keyfile)
        if p.exists():
            key = win32crypt.CryptUnprotectData(p.read_bytes(), None, None, None, UI_FORBIDDEN)[1]
        else:
            key = secrets.token_bytes(32)
            p.write_bytes(win32crypt.CryptProtectData(key, "Deja", None, None, None, UI_FORBIDDEN))
        self._enc, self._mac, self._idx = (hashlib.sha256(key + label).digest() for label in (b"enc", b"mac", b"idx"))

    # shortcut: SHAKE-256 keystream + HMAC-SHA256 (encrypt-then-MAC) because the standard library has no AES;
    # move to AES-GCM from `cryptography` if this ever ships beyond a personal tool
    def seal(self, data):
        nonce = secrets.token_bytes(16)
        ct = _xor(data, hashlib.shake_256(self._enc + nonce).digest(len(data)))
        return nonce + ct + hmac.new(self._mac, nonce + ct, "sha256").digest()[:16]

    def open(self, blob):
        nonce, ct, tag = blob[:16], blob[16:-16], blob[-16:]
        if not hmac.compare_digest(tag, hmac.new(self._mac, nonce + ct, "sha256").digest()[:16]):
            raise ValueError("this file was changed or belongs to another Windows account")
        return _xor(ct, hashlib.shake_256(self._enc + nonce).digest(len(ct)))

    def seal_text(self, s):
        return None if s is None else self.seal(s.encode())

    def open_text(self, blob):
        return None if blob is None else self.open(blob).decode()

    def tokens(self, text):
        """One keyed hash per three-letter piece, in order: a phrase query of them is a substring match."""
        s = (text or "").lower()
        return " ".join(hashlib.blake2b(s[i:i + 3].encode(), digest_size=6, key=self._idx).hexdigest()
                        for i in range(len(s) - 2))
