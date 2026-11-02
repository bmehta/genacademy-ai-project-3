import json
import sqlite3
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, session_id TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL, payload TEXT NOT NULL, decision TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add_session(self, sid):
        with self.connect() as db:
            db.execute('INSERT INTO sessions(id,created_at) VALUES(?,?)', (sid, now()))

    def sessions(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100')]

    def exists(self, sid):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM sessions WHERE id=?', (sid,)).fetchone() is not None

    def closed(self, sid):
        with self.connect() as db:
            return bool(db.execute('SELECT closed FROM sessions WHERE id=?', (sid,)).fetchone()['closed'])

    def close(self, sid):
        with self.connect() as db:
            db.execute('UPDATE sessions SET closed=1 WHERE id=?', (sid,))

    def ticket(self, sid, payload, fail=False):
        with self.connect() as db:
            existing = db.execute('SELECT id FROM tickets WHERE session_id=?', (sid,)).fetchone()
            if existing:
                return existing['id']
            if fail:
                raise TimeoutError('Simulated ticket database timeout')
            ticket_id = 'IT-' + sid[:8].upper()
            db.execute('INSERT INTO tickets VALUES(?,?,?,?,?,?,?)',
                       (ticket_id, sid, 'pending', json.dumps(payload), None, now(), now()))
            return ticket_id

    def decide(self, sid, decision):
        with self.connect() as db:
            db.execute('UPDATE tickets SET status=?,decision=?,updated_at=? WHERE session_id=?',
                       (decision['decision'], json.dumps(decision), now(), sid))

    def tickets(self):
        with self.connect() as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM tickets ORDER BY created_at DESC')]
        for row in rows:
            row['payload'] = json.loads(row['payload'])
            row['decision'] = json.loads(row['decision']) if row['decision'] else None
        return rows
