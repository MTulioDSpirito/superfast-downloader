"""db.py — camada de persistência (SQLite, stdlib).

Modelo mínimo p/ o SuperFast DM:
  downloads  — 1 linha por tarefa (histórico + config resumida)
  segments   — estado por segmento (p/ retomada)
  config     — key/value

NOTA (thread-safety): usa UMA conexão compartilhada (check_same_thread=False)
protegida por um lock por instância + commit após cada escrita. Usar conexões
efêmeras (abrir/fechar por op) causava deadlock de lock de escrita entre threads
(a conexão órfã segurava o lock de write do SQLite enquanto a thread esperava
o lock do módulo). Conexão única elimina a disputa entre conexões.
"""
import os
import sqlite3
import threading


class DB:
    def __init__(self, path):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS downloads(
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    filename TEXT,
                    path TEXT,
                    total INTEGER DEFAULT 0,
                    done INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    connections INTEGER DEFAULT 8,
                    speed REAL DEFAULT 0,
                    error TEXT,
                    created REAL,
                    finished REAL
                );
                CREATE TABLE IF NOT EXISTS segments(
                    task_id INTEGER NOT NULL,
                    idx INTEGER NOT NULL,
                    start INTEGER NOT NULL,
                    end INTEGER NOT NULL,
                    next INTEGER NOT NULL,
                    PRIMARY KEY(task_id, idx)
                );
                CREATE TABLE IF NOT EXISTS config(
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            self._conn.commit()

    def _exec(self, sql, args=()):
        """Executa escrita, commita, retorna lastrowid (se houver)."""
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur.lastrowid

    def _query(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def _one(self, sql, args=()):
        with self._lock:
            r = self._conn.execute(sql, args).fetchone()
            return dict(r) if r else None

    # ---------- config ----------
    def get_config(self, key, default=None):
        r = self._one("SELECT value FROM config WHERE key=?", (key,))
        return r["value"] if r else default

    def set_config(self, key, value):
        self._exec(
            "INSERT INTO config(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    # ---------- downloads ----------
    def add_download(self, url, filename, path, connections, now):
        return self._exec(
            "INSERT INTO downloads(url,filename,path,total,done,status,connections,created)"
            " VALUES(?,?,?,0,0,'pending',?,?)",
            (url, filename, path, connections, now),
        )

    def get_tasks(self):
        return self._query("SELECT * FROM downloads ORDER BY id DESC")

    def get_task(self, tid):
        return self._one("SELECT * FROM downloads WHERE id=?", (tid,))

    def set_task(self, tid, **fields):
        if not fields:
            return
        keys = ",".join(f"{k}=?" for k in fields)
        self._exec(f"UPDATE downloads SET {keys} WHERE id=?",
                   list(fields.values()) + [tid])

    def set_status(self, tid, status, error=None, finished=None):
        self._exec(
            "UPDATE downloads SET status=?, error=?, "
            "finished=COALESCE(?, finished) WHERE id=?",
            (status, error, finished, tid),
        )

    def set_done(self, tid, done):
        self._exec("UPDATE downloads SET done=? WHERE id=?", (done, tid))

    def set_total(self, tid, total):
        self._exec("UPDATE downloads SET total=? WHERE id=?", (total, tid))

    def set_speed(self, tid, speed):
        self._exec("UPDATE downloads SET speed=? WHERE id=?", (speed, tid))

    # ---------- segments ----------
    def set_segments(self, tid, segments):
        with self._lock:
            self._conn.execute("DELETE FROM segments WHERE task_id=?", (tid,))
            self._conn.executemany(
                "INSERT INTO segments(task_id,idx,start,end,next) VALUES(?,?,?,?,?)",
                [(tid, i, s, (-1 if e is None else e), n)
                 for i, (s, e, n) in enumerate(segments)],
            )
            self._conn.commit()

    def get_segments(self, tid):
        rows = self._query(
            "SELECT idx,start,end,next FROM segments WHERE task_id=? ORDER BY idx",
            (tid,))
        return [(r["idx"], r["start"], r["end"], r["next"]) for r in rows]

    def set_segment_next(self, tid, idx, nxt):
        self._exec("UPDATE segments SET next=? WHERE task_id=? AND idx=?",
                   (nxt, tid, idx))
