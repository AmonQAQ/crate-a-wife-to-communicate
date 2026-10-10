"""SQLite 存储：对话记录、长期记忆、提醒、文本处理规则。"""
import re
import sqlite3
import threading
import time

from . import paths


class Database:
    def __init__(self, path=None):
        self.path = str(path or paths.DB_PATH)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock, self._conn:
            self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                role TEXT NOT NULL,
                mode TEXT NOT NULL,
                content TEXT NOT NULL,
                jp TEXT,
                think_ms REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                category TEXT,
                value TEXT,
                updated REAL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                remind_at REAL,
                on_startup INTEGER DEFAULT 0,
                done INTEGER DEFAULT 0,
                created REAL
            );
            CREATE TABLE IF NOT EXISTS text_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                pattern TEXT,
                replacement TEXT,
                created REAL
            );
            """)
            # 迁移：给旧库补 voice 列（语音文件路径）
            try:
                self._conn.execute("ALTER TABLE messages ADD COLUMN voice TEXT")
            except Exception:
                pass

    # ---------------- 对话 ----------------
    def add_message(self, role, mode, content, jp=None, think_ms=0.0, voice=None):
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO messages(ts,role,mode,content,jp,think_ms,voice) VALUES(?,?,?,?,?,?,?)",
                (time.time(), role, mode, content, jp, think_ms, voice))
            return cur.lastrowid

    def set_message_voice(self, mid, voice):
        if not mid:
            return
        with self._lock, self._conn:
            self._conn.execute("UPDATE messages SET voice=? WHERE id=?", (voice, mid))

    def recent_messages(self, limit=40, mode=None):
        q = "SELECT * FROM messages"
        args = []
        if mode:
            q += " WHERE mode=?"
            args.append(mode)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = list(self._conn.execute(q, args).fetchall())
        rows.reverse()
        return rows

    def count_messages(self):
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    def migrate_persona_modes(self):
        """历史模式迁移：qa/chat → kato；eriri/utaha → rem/elaina。"""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE messages SET mode='kato' WHERE mode IN ('qa','chat')")
            self._conn.execute(
                "UPDATE messages SET mode='rem' WHERE mode='eriri'")
            self._conn.execute(
                "UPDATE messages SET mode='elaina' WHERE mode='utaha'")

    def search_messages(self, keyword="", mode=None, offset=0, limit=200):
        """按关键字/模式分页查询历史消息（时间倒序）。"""
        q = "SELECT * FROM messages"
        conds, args = [], []
        if mode:
            conds.append("mode=?")
            args.append(mode)
        if keyword:
            conds.append("(content LIKE ? OR jp LIKE ?)")
            args += [f"%{keyword}%", f"%{keyword}%"]
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        with self._lock:
            return list(self._conn.execute(q, args).fetchall())

    def cleanup_messages(self, keep=100):
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM messages WHERE id NOT IN "
                "(SELECT id FROM messages ORDER BY id DESC LIMIT ?)", (keep,))
            return cur.rowcount

    def clear_messages(self):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM messages")

    # ---------------- 长期记忆 ----------------
    def set_memory(self, key, value, category="general"):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO memories(key,category,value,updated) VALUES(?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "category=excluded.category, updated=excluded.updated",
                (key, category, value, time.time()))

    def get_memory(self, key):
        with self._lock:
            row = self._conn.execute("SELECT value FROM memories WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def del_memory(self, key):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM memories WHERE key=?", (key,))

    def list_memories(self, category=None):
        q = "SELECT * FROM memories"
        args = []
        if category:
            q += " WHERE category=?"
            args.append(category)
        q += " ORDER BY updated DESC"
        with self._lock:
            return list(self._conn.execute(q, args).fetchall())

    # ---------------- 提醒 ----------------
    def add_reminder(self, text, remind_at=None, on_startup=False):
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO reminders(text,remind_at,on_startup,done,created) VALUES(?,?,?,0,?)",
                (text, remind_at, 1 if on_startup else 0, time.time()))
            return cur.lastrowid

    def due_reminders(self, now=None):
        now = now or time.time()
        with self._lock:
            return list(self._conn.execute(
                "SELECT * FROM reminders WHERE done=0 AND "
                "((remind_at IS NOT NULL AND remind_at<=?) OR (on_startup=1 AND remind_at IS NULL))",
                (now,)).fetchall())

    def mark_reminder_done(self, rid):
        with self._lock, self._conn:
            self._conn.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))

    def list_reminders(self, done=0):
        with self._lock:
            return list(self._conn.execute(
                "SELECT * FROM reminders WHERE done=? ORDER BY remind_at", (done,)).fetchall())

    # ---------------- 文本规则 ----------------
    def add_rule(self, name, pattern, replacement):
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO text_rules(name,pattern,replacement,created) VALUES(?,?,?,?)",
                (name, pattern, replacement, time.time()))
            return cur.lastrowid

    def list_rules(self):
        with self._lock:
            return list(self._conn.execute("SELECT * FROM text_rules ORDER BY id").fetchall())

    def del_rule(self, rid):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM text_rules WHERE id=?", (rid,))

    def apply_rules(self, text):
        out = text
        for r in self.list_rules():
            try:
                out = re.sub(r["pattern"], r["replacement"], out)
            except Exception:
                pass
        return out
