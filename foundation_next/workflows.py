"""Original durable workflow engine for FoundationCentar Next.

Explicit capability handlers; no mock completion or implicit remote execution.
SQLite provides durable state and event history for single-process deployments.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


@contextlib.contextmanager
def _managed_connection(database_path: str):
    """Open a SQLite connection, ensure it is closed on exit.

    Python's sqlite3.Connection context manager only commits/rollbacks —
    it does not close the file handle. Windows cannot delete a file that
    is still open, so we wrap it with a closing context manager. We also
    explicitly commit after each use so data is durable before the
    connection is closed.
    """
    db = sqlite3.connect(database_path, timeout=10)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowError(RuntimeError):
    pass


class WorkflowEngine:
    def __init__(self, database_path: str):
        self.database_path = database_path
        with _managed_connection(self.database_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, capability TEXT NOT NULL, action TEXT NOT NULL,
                principal TEXT NOT NULL, arguments TEXT NOT NULL,
                status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id))""")

    def _connect(self):
        return _managed_connection(self.database_path)

    def submit(self, *, principal: str, capability: str, action: str,
               arguments: dict[str, Any]) -> str:
        if not all([principal, capability, action]) or not isinstance(arguments, dict):
            raise ValueError("Invalid workflow request")
        job_id = str(uuid.uuid4())
        now = utc_now()
        with self._connect() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                       (job_id, capability, action, principal, json.dumps(arguments),
                        "pending", None, now, now))
            db.execute("INSERT INTO events(job_id,status,created_at) VALUES (?,?,?)",
                       (job_id, "pending", now))
        return job_id

    def get(self, job_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        keys = ("id", "capability", "action", "principal", "arguments",
                "status", "result", "created_at", "updated_at")
        item = dict(zip(keys, row, strict=True))
        item["arguments"] = json.loads(item["arguments"])
        item["result"] = json.loads(item["result"]) if item["result"] else None
        return item

    def run(self, job_id: str, executor: Callable[..., dict[str, Any]]) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status='running',updated_at=? WHERE id=? AND status='pending'",
                (utc_now(), job_id))
            if cursor.rowcount != 1:
                raise WorkflowError("Job missing or not pending")
            db.execute("INSERT INTO events(job_id,status,created_at) VALUES (?,?,?)",
                       (job_id, "running", utc_now()))
        job = self.get(job_id)
        try:
            result = executor(capability=job["capability"], principal=job["principal"],
                              action=job["action"], arguments=job["arguments"])
            if not isinstance(result, dict) or result.get("status") != "success":
                raise WorkflowError("Executor did not report verified success")
        except Exception as exc:
            self._finish(job_id, "failed", {"error": type(exc).__name__})
            raise
        self._finish(job_id, "completed", result)
        return result

    def _finish(self, job_id: str, status: str, result: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?,result=?,updated_at=? WHERE id=? AND status='running'",
                (status, json.dumps(result), utc_now(), job_id),
            )
            db.execute("INSERT INTO events(job_id,status,created_at) VALUES (?,?,?)",
                       (job_id, status, utc_now()))

    def history(self, job_id: str) -> list[str]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT status FROM events WHERE job_id=? ORDER BY seq", (job_id,)
            ).fetchall()
        return [row[0] for row in rows]
