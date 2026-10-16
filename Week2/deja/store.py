"""Everything Déjà remembers: one SQLite file with full-text search, plus the
screenshots next to it. Window titles, screen text, notes and screenshots are all
encrypted (see vault.py); only app names and times are kept in the clear, for the
day chart. Nothing here ever leaves the machine.
"""
import re
import sqlite3
import threading
import time
from pathlib import Path

from .vault import Vault

SCHEMA = """
create table if not exists frames(id integer primary key, t real, app text, title blob, image text, text blob);
create index if not exists frames_t on frames(t);
create virtual table if not exists frames_fts using fts5(text, title, app, tokenize='ascii');
create table if not exists notes(id integer primary key, t real, text blob, kind text, due real, done integer default 0, fired integer default 0);
create virtual table if not exists notes_fts using fts5(text, tokenize='ascii');
"""


def words(terms):
    """The searchable pieces: "orders.py" -> orders; anything under three letters can't be indexed."""
    return sorted({p for w in terms for p in re.split(r"[^\w]+", w.lower()) if len(p) >= 3})


class Store:
    def __init__(self, home):
        self.home = Path(home)
        (self.home / "frames").mkdir(parents=True, exist_ok=True)
        self.vault = Vault(self.home / "key.dpapi")
        self.db = sqlite3.connect(self.home / "memory.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("pragma journal_mode=wal")
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()
        if (self.home / "deja.db").exists():
            self._migrate(self.home / "deja.db")

    def fts_query(self, terms):
        """OR of substrings ("error" finds "ConnectionError"); more matches rank higher."""
        return " OR ".join(f'"{self.vault.tokens(w)}"' for w in words(terms))

    def _q(self, sql, args=()):
        with self.lock:
            rows = [dict(r) for r in self.db.execute(sql, args)]
        for r in rows:
            for k in ("title", "text"):
                if isinstance(r.get(k), bytes):
                    r[k] = self.vault.open_text(r[k])
        return rows

    def _img(self, rel):
        return self.home / "frames" / Path(rel).with_suffix(".enc")

    def put_image(self, rel, jpeg):
        p = self._img(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.vault.seal(jpeg))

    def image(self, rel):
        p = self._img(rel)
        return self.vault.open(p.read_bytes()) if p.exists() else None

    def add_frame(self, t, app, title, image, text):
        v = self.vault
        with self.lock, self.db:
            cur = self.db.execute("insert into frames(t, app, title, image, text) values (?,?,?,?,?)",
                                  (t, app, v.seal_text(title), image, v.seal_text(text)))
            self.db.execute("insert into frames_fts(rowid, text, title, app) values (?,?,?,?)",
                            (cur.lastrowid, v.tokens(text), v.tokens(title), v.tokens(app)))
            return cur.lastrowid

    def search(self, terms, start=None, end=None, limit=8):
        q = self.fts_query(terms)
        if not q:
            return self.timeline(start, end, limit)
        return self._q(
            "select f.id, f.t, f.app, f.title, f.image, f.text, bm25(frames_fts, 1.0, 2.0, 0.5) as score "
            "from frames_fts join frames f on f.id = frames_fts.rowid "
            "where frames_fts match ? and f.t >= ? and f.t < ? order by score limit ?",
            (q, start or 0, end or 9e12, limit))

    def timeline(self, start=None, end=None, limit=500):
        """Evenly thinned when the window holds more frames than the limit."""
        with self.lock:
            rows = self.db.execute("select id from frames where t >= ? and t < ? order by t",
                                   (start or 0, end or 9e12)).fetchall()
        step = max(1, len(rows) // limit) if limit else 1
        ids = [r[0] for r in rows[::step][:limit]]
        out = self._q(f"select id, t, app, title, image, text from frames where id in ({','.join('?' * len(ids))}) "
                      "order by t", ids) if ids else []
        for r in out:
            r["text"] = (r["text"] or "")[:240]
        return out

    def frame(self, fid):
        rows = self._q("select * from frames where id = ?", (fid,))
        return rows[0] if rows else None

    def add_note(self, text, kind, due=None, t=None):
        with self.lock, self.db:
            cur = self.db.execute("insert into notes(t, text, kind, due) values (?,?,?,?)",
                                  (t or time.time(), self.vault.seal_text(text), kind, due))
            self.db.execute("insert into notes_fts(rowid, text) values (?,?)", (cur.lastrowid, self.vault.tokens(text)))
            return cur.lastrowid

    def notes(self, include_done=False):
        return self._q("select * from notes" + ("" if include_done else " where done = 0") +
                       " order by coalesce(due, 9e12), t desc")

    def search_notes(self, terms, limit=5):
        q = self.fts_query(terms)
        if not q:
            return []
        return self._q("select n.* from notes_fts join notes n on n.id = notes_fts.rowid "
                       "where notes_fts match ? order by bm25(notes_fts) limit ?", (q, limit))

    def due_now(self, now=None):
        return self._q("select * from notes where done = 0 and fired = 0 and due is not null and due <= ?",
                       (now or time.time(),))

    def mark_fired(self, nid):
        with self.lock, self.db:
            self.db.execute("update notes set fired = 1 where id = ?", (nid,))

    def set_done(self, nid, done=True):
        with self.lock, self.db:
            self.db.execute("update notes set done = ? where id = ?", (int(done), nid))

    def delete_note(self, nid):
        with self.lock, self.db:
            self.db.execute("delete from notes where id = ?", (nid,))
            self.db.execute("delete from notes_fts where rowid = ?", (nid,))

    def forget(self, since=None, before=None):
        """Delete frames in [since, before) and their images. Returns how many."""
        since, before = since or 0, before or 9e12
        with self.lock, self.db:
            rows = self.db.execute("select id, image from frames where t >= ? and t < ?", (since, before)).fetchall()
            ids = [(r["id"],) for r in rows]
            self.db.executemany("delete from frames where id = ?", ids)
            self.db.executemany("delete from frames_fts where rowid = ?", ids)
        for r in rows:
            self._img(r["image"]).unlink(missing_ok=True)
        return len(rows)

    def stats(self):
        midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        with self.lock:
            r = self.db.execute("select count(*) as n, sum(t >= ?) as today, max(t) as last from frames",
                                (midnight,)).fetchone()
        size = sum(p.stat().st_size for p in (self.home / "frames").rglob("*.enc"))
        size += (self.home / "memory.db").stat().st_size
        return {"frames": r["n"], "today": r["today"] or 0, "last": r["last"], "mb": round(size / 2**20, 1)}

    def _migrate(self, old_path):
        """Encrypt a store from before encryption, then delete the readable copy."""
        old = sqlite3.connect(old_path)
        old.row_factory = sqlite3.Row
        for f in old.execute("select * from frames order by t"):
            jpg = self.home / "frames" / f["image"]
            if jpg.exists():
                self.put_image(f["image"], jpg.read_bytes())
                self.add_frame(f["t"], f["app"], f["title"], f["image"], f["text"])
                jpg.unlink()
        for n in old.execute("select * from notes"):
            nid = self.add_note(n["text"], n["kind"], n["due"], n["t"])
            with self.lock, self.db:
                self.db.execute("update notes set done = ?, fired = ? where id = ?", (n["done"], n["fired"], nid))
        old.close()
        for suffix in ("", "-wal", "-shm"):
            Path(str(old_path) + suffix).unlink(missing_ok=True)
