import unittest

from foundation_next.agentguard_adapter import AgentGuardAdapter
from foundation_next.agentguard_execution import GuardedExecution
from foundation_next.orchestrator import IntegrationError


class AgentGuardContractTests(unittest.TestCase):
    def test_actual_toolcall_payload(self):
        requests = []
        def transport(url, payload):
            requests.append((url, payload))
            return {"decision": "ALLOWED", "audit_id": 42}
        adapter = AgentGuardAdapter("https://guard.example/toolcall", agent="foundation", transport=transport)
        self.assertEqual(adapter.authorize(capability="rag", action="query", arguments={})["audit_id"], 42)
        self.assertEqual(requests[0][1]["tool"], "rag")
        self.assertEqual(requests[0][1]["agent"], "foundation")
        self.assertIn("action", requests[0][1]["input"])

    def test_denials_fail_closed(self):
        for decision in ("DENIED", "APPROVAL_REQUIRED", "RATE_LIMITED"):
            adapter = AgentGuardAdapter("https://guard.example/toolcall", agent="foundation",
                transport=lambda *_: {"decision": decision, "audit_id": 1})
            with self.assertRaises(IntegrationError):
                adapter.authorize(capability="rag", action="query", arguments={})

    def test_missing_audit_id_fails(self):
        adapter = AgentGuardAdapter("https://guard.example/toolcall", agent="foundation",
            transport=lambda *_: {"decision": "ALLOWED"})
        with self.assertRaises(IntegrationError):
            adapter.authorize(capability="rag", action="query", arguments={})

    def test_guard_denial_prevents_execution(self):
        calls = []
        adapter = AgentGuardAdapter("https://guard.example/toolcall", agent="foundation",
            transport=lambda *_: {"decision": "DENIED", "audit_id": 3})
        bridge = GuardedExecution(adapter, {"rag": lambda payload: calls.append(payload)})
        with self.assertRaises(IntegrationError):
            bridge.execute(principal="alice", capability="rag", action="query", arguments={})
        self.assertEqual(calls, [])

    def test_authorized_dispatch_preserves_audit_reference(self):
        adapter = AgentGuardAdapter("https://guard.example/toolcall", agent="foundation",
            transport=lambda *_: {"decision": "ALLOWED", "audit_id": 5})
        bridge = GuardedExecution(adapter, {"rag": lambda payload: {"status": "success", "audit": payload["guard_audit_id"]}})
        result = bridge.execute(principal="alice", capability="rag", action="query", arguments={})
        self.assertEqual(result["audit"], 5)
