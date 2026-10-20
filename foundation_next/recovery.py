"""Safe workflow recovery: do not automatically replay interrupted side effects."""
import json

from foundation_next.workflows import WorkflowEngine, utc_now


def mark_interrupted(workflows: WorkflowEngine) -> list[str]:
    """Quarantine running jobs after a verified single-worker restart.

    Caller must ensure no worker is currently executing jobs against this DB.
    Returns affected IDs. No executor is called; manual reconciliation is required.
    """
    now = utc_now()
    with workflows._connect() as db:
        rows = db.execute("SELECT id FROM jobs WHERE status='running' ORDER BY id").fetchall()
        ids = [row[0] for row in rows]
        for job_id in ids:
            cursor = db.execute(
                "UPDATE jobs SET status='failed',result=?,updated_at=? "
                "WHERE id=? AND status='running'",
                (json.dumps({"error": "InterruptedExecution", "reconcile": True}), now, job_id),
            )
            if cursor.rowcount == 1:
                db.execute(
                    "INSERT INTO events(job_id,status,created_at) VALUES (?,?,?)",
                    (job_id, "failed", now),
                )
    return ids
