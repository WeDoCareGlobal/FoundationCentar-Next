"""SQLite-backed audit event journal with hash chaining.

Integrity verification detects edits to retained rows. It cannot detect
complete deletion or replacement without an external trusted checkpoint.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from foundation_next.workflows import utc_now


@contextmanager
def _conn(path: str):
    db = sqlite3.connect(path, timeout=10)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        yield db
        db.commit()
    finally:
        db.close()


class AuditJournal:
    def __init__(self, path: str):
        self.path = path
        with _conn(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS audit_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                digest TEXT NOT NULL)""")

    @staticmethod
    def _digest(seq, timestamp, actor, action, resource, previous):
        payload = json.dumps([seq, timestamp, actor, action, resource, previous],
                             ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def append(self, *, actor: str, action: str, resource: str) -> int:
        if not actor or not action or not resource:
            raise ValueError("Audit fields required")
        with _conn(self.path) as db:
            previous_row = db.execute(
                "SELECT digest FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
            previous = previous_row[0] if previous_row else "GENESIS"
            timestamp = utc_now()
            next_seq = db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM audit_events").fetchone()[0]
            digest = self._digest(next_seq, timestamp, actor, action, resource, previous)
            db.execute("""INSERT INTO audit_events
                (seq,timestamp,actor,action,resource,previous_hash,digest)
                VALUES (?,?,?,?,?,?,?)""",
                (next_seq, timestamp, actor, action, resource, previous, digest))
            return next_seq

    def _connect(self):
        return _conn(self.path)

    def verify(self) -> bool:
        with _conn(self.path) as db:
            rows = db.execute("""SELECT seq,timestamp,actor,action,resource,previous_hash,digest
                                  FROM audit_events ORDER BY seq""").fetchall()
        previous = "GENESIS"
        for index, row in enumerate(rows, start=1):
            seq, timestamp, actor, action, resource, previous_hash, digest = row
            if seq != index or previous_hash != previous:
                return False
            if digest != self._digest(seq, timestamp, actor, action, resource, previous):
                return False
            previous = digest
        return True
