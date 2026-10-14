import unittest

from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError, Service


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.guard = Service("agentguard", "https://guard.example.test/authorize")
        self.cap = {"rag": Service("rag", "https://rag.example.test/execute")}

    def test_denied_never_executes(self):
        calls = []
        def transport(url, payload):
            calls.append(url)
            return {"decision": "deny"}
        app = FoundationOrchestrator(self.guard, self.cap, transport=transport)
        with self.assertRaises(IntegrationError):
            app.execute(capability="rag", principal="user1", action="query", arguments={})
        self.assertEqual(calls, [self.guard.url])

    def test_authorized_execution(self):
        def transport(url, payload):
            if url == self.guard.url:
                return {"decision": "allow", "decision_id": "signed-decision-placeholder"}
            self.assertEqual(payload["guard_decision_id"], "signed-decision-placeholder")
            return {"status": "success", "result": {"answer": "ok"}}
        app = FoundationOrchestrator(self.guard, self.cap, transport=transport)
        result = app.execute(capability="rag", principal="user1", action="query", arguments={})
        self.assertEqual(result["result"]["answer"], "ok")

    def test_unknown_capability_fails_closed(self):
        app = FoundationOrchestrator(self.guard, self.cap, transport=lambda *_: self.fail("unexpected network"))
        with self.assertRaises(IntegrationError):
            app.execute(capability="shell", principal="user1", action="run", arguments={})

    def test_missing_guard_decision_id_fails(self):
        app = FoundationOrchestrator(self.guard, self.cap, transport=lambda *_: {"decision": "allow"})
        with self.assertRaises(IntegrationError):
            app.execute(capability="rag", principal="user1", action="query", arguments={})


if __name__ == "__main__":
    unittest.main()
