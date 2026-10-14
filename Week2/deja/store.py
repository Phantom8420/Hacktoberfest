"""Everything Déjà remembers: one SQLite file with full-text search, plus the
screenshots as JPEGs next to it. Nothing here ever leaves the machine.
"""
import re
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
create table if not exists frames(id integer primary key, t real, app text, title text, image text, text text);
create index if not exists frames_t on frames(t);
create virtual table if not exists frames_fts using fts5(text, title, app, tokenize='trigram');
create table if not exists notes(id integer primary key, t real, text text, kind text, due real, done integer default 0, fired integer default 0);
create virtual table if not exists notes_fts using fts5(text, tokenize='trigram');
"""


def fts_query(terms):
    """OR of substrings (trigram index: "error" finds "ConnectionError"); more matches rank higher."""
    words = {p for w in terms for p in re.split(r"[^\w]+", w.lower()) if len(p) >= 3}
    return " OR ".join(f'"{w}"' for w in sorted(words))


class Store:
    def __init__(self, home):
        self.home = Path(home)
        (self.home / "frames").mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.home / "deja.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("pragma journal_mode=wal")
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()

    def _q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args)]

    def add_frame(self, t, app, title, image, text):
        with self.lock, self.db:
            cur = self.db.execute("insert into frames(t, app, title, image, text) values (?,?,?,?,?)",
                                  (t, app, title, image, text))
            self.db.execute("insert into frames_fts(rowid, text, title, app) values (?,?,?,?)",
                            (cur.lastrowid, text, title, app))
            return cur.lastrowid

    def search(self, terms, start=None, end=None, limit=8):
        q = fts_query(terms)
        if not q:
            return self.timeline(start, end, limit)
        return self._q(
            "select f.id, f.t, f.app, f.title, f.image, f.text, bm25(frames_fts, 1.0, 2.0, 0.5) as score "
            "from frames_fts join frames f on f.id = frames_fts.rowid "
            "where frames_fts match ? and f.t >= ? and f.t < ? order by score limit ?",
            (q, start or 0, end or 9e12, limit))

    def timeline(self, start=None, end=None, limit=500):
        """Evenly thinned when the window holds more frames than the limit."""
        rows = self._q("select id, t, app, title, image, substr(text, 1, 240) as text from frames "
                       "where t >= ? and t < ? order by t", (start or 0, end or 9e12))
        step = max(1, len(rows) // limit) if limit else 1
        return rows[::step][:limit]

    def frame(self, fid):
        rows = self._q("select * from frames where id = ?", (fid,))
        return rows[0] if rows else None

    def add_note(self, text, kind, due=None, t=None):
        with self.lock, self.db:
            cur = self.db.execute("insert into notes(t, text, kind, due) values (?,?,?,?)",
                                  (t or time.time(), text, kind, due))
            self.db.execute("insert into notes_fts(rowid, text) values (?,?)", (cur.lastrowid, text))
            return cur.lastrowid

    def notes(self, include_done=False):
        return self._q("select * from notes" + ("" if include_done else " where done = 0") +
                       " order by coalesce(due, 9e12), t desc")

    def search_notes(self, terms, limit=5):
        q = fts_query(terms)
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
            (self.home / "frames" / r["image"]).unlink(missing_ok=True)
        return len(rows)

    def stats(self):
        midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        r = self._q("select count(*) as n, sum(t >= ?) as today, max(t) as last from frames", (midnight,))[0]
        size = sum(p.stat().st_size for p in (self.home / "frames").rglob("*.jpg"))
        size += (self.home / "deja.db").stat().st_size
        return {"frames": r["n"], "today": r["today"] or 0, "last": r["last"], "mb": round(size / 2**20, 1)}
