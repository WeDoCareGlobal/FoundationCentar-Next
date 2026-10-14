import os
import tempfile
import unittest

from foundation_next.workflows import WorkflowEngine, WorkflowError


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "state.db")
        self.engine = WorkflowEngine(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_success_is_durable(self):
        job = self.engine.submit(principal="alice", capability="rag", action="query", arguments={"q": "x"})
        result = self.engine.run(job, lambda **kw: {"status": "success", "output": kw["arguments"]})
        self.assertEqual(result["output"], {"q": "x"})
        reopened = WorkflowEngine(self.path)
        self.assertEqual(reopened.get(job)["status"], "completed")
        self.assertEqual(reopened.history(job), ["pending", "running", "completed"])

    def test_failure_never_marks_completed(self):
        job = self.engine.submit(principal="alice", capability="rag", action="query", arguments={})
        with self.assertRaises(WorkflowError):
            self.engine.run(job, lambda **kw: {"status": "mock"})
        self.assertEqual(self.engine.get(job)["status"], "failed")

    def test_job_cannot_execute_twice(self):
        job = self.engine.submit(principal="alice", capability="rag", action="query", arguments={})
        self.engine.run(job, lambda **kw: {"status": "success"})
        with self.assertRaises(WorkflowError):
            self.engine.run(job, lambda **kw: {"status": "success"})

    def test_invalid_request(self):
        with self.assertRaises(ValueError):
            self.engine.submit(principal="", capability="rag", action="query", arguments={})


if __name__ == "__main__":
    unittest.main()
