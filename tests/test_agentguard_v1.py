import unittest

from foundation_next.agentguard_v1 import AgentGuardV1Execution
from foundation_next.orchestrator import IntegrationError


class AgentGuardV1Tests(unittest.TestCase):
    def client(self, transport):
        return AgentGuardV1Execution(
            "https://guard.example/v1/execute", agent="foundation",
            api_key="test-key", transport=transport,
        )

    def test_contract_and_single_execution(self):
        requests = []
        def transport(url, payload, key):
            requests.append((url, payload, key))
            return {"decision": "ALLOW", "result": {"status": "success", "value": 7}}
        result = self.client(transport).execute(
            capability="rag", action="query", arguments={"q": "test"}, request_id="req-1",
        )
        self.assertEqual(result["value"], 7)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1], {
            "agent": "foundation", "tool": "rag", "request_id": "req-1",
            "payload": {"action": "query", "arguments": {"q": "test"}}, "approval": None,
        })
        self.assertEqual(requests[0][2], "test-key")

    def test_fail_closed(self):
        for response in (
            {"decision": "DENY", "reason": "policy"},
            {"decision": "APPROVAL_REQUIRED"},
            {"decision": "ERROR"},
            {"decision": "ALLOW"},
            {"decision": "ALLOWED", "result": {}},
            None,
        ):
            with self.subTest(response=response), self.assertRaises(IntegrationError):
                self.client(lambda *_: response).execute(capability="rag", action="query", arguments={})

    def test_transport_failure(self):
        def broken(*_):
            raise ConnectionError("down")
        with self.assertRaises(IntegrationError):
            self.client(broken).execute(capability="rag", action="query", arguments={})

    def test_approval_forwarded_without_local_bypass(self):
        calls = []
        def transport(_, payload, __):
            calls.append(payload)
            return {"decision": "DENY", "reason": "approval_missing_or_invalid"}
        with self.assertRaises(IntegrationError):
            self.client(transport).execute(
                capability="rag", action="query", arguments={}, approval="token", request_id="req-2",
            )
        self.assertEqual(calls[0]["approval"], "token")

    def test_reject_insecure_remote_endpoint(self):
        with self.assertRaises(ValueError):
            AgentGuardV1Execution("http://guard.example/v1/execute", agent="a", api_key="key")
