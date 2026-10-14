import os
import tempfile
import unittest

from foundation_next.recovery import mark_interrupted
from foundation_next.workflows import WorkflowEngine, utc_now


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = WorkflowEngine(os.path.join(self.tmp.name, "workflow.db"))

    def test_interrupted_job_quarantined_without_reexecution(self):
        job_id = self.engine.submit(principal="alice", capability="rag", action="query", arguments={})
        with self.engine._connect() as db:
            db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?", (utc_now(), job_id))
        self.assertEqual(mark_interrupted(self.engine), [job_id])
        self.assertEqual(self.engine.get(job_id)["status"], "failed")
        self.assertTrue(self.engine.get(job_id)["result"]["reconcile"])
        self.assertEqual(mark_interrupted(self.engine), [])

    def test_pending_job_remains_pending(self):
        job_id = self.engine.submit(principal="alice", capability="rag", action="query", arguments={})
        self.assertEqual(mark_interrupted(self.engine), [])
        self.assertEqual(self.engine.get(job_id)["status"], "pending")
