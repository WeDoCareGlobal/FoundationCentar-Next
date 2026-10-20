import os
import tempfile
import unittest
from foundation_next.agents import AgentRegistry, AgentSpec
from foundation_next.control_plane import FoundationControlPlane
from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError, Service
from foundation_next.workflows import WorkflowEngine


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workflows = WorkflowEngine(os.path.join(self.tmp.name, "jobs.db"))
        self.agents = AgentRegistry()
        self.agents.register(AgentSpec("rag-agent", frozenset({"rag"})), lambda *_: {"status": "success"})
        self.guard_service = Service("guard", "https://guard.example.test/check")
        self.capabilities = {"rag": Service("rag", "https://rag.example.test/execute")}
        from foundation_next.omniguard_client import OmniGuardClient, OmniGuardDecision, OmniGuardResult
        self.mock_omni_client = OmniGuardClient(
            base_url="http://localhost:8000/v1",
            api_key="test-key-for-unittests-only",
        )
        # Mock inspect to return ALLOW for authorized tests
        import asyncio
        async def mock_inspect_allow(messages=None, **kwargs):
            return OmniGuardResult(
                decision=OmniGuardDecision.ALLOW,
                confidence=1.0,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason=None,
            )
        self.mock_omni_client.inspect = mock_inspect_allow

    def tearDown(self):
        self.tmp.cleanup()

    def test_authorized_job(self):
        calls = []
        def transport(url, payload):
            calls.append(url)
            if url == self.guard_service.url:
                return {"decision": "allow", "decision_id": "d-1"}
            return {"status": "success", "answer": "retrieved"}
        app = FoundationControlPlane(self.workflows, FoundationOrchestrator(
            self.guard_service, self.capabilities, transport=transport), self.agents, omni_guard_client=self.mock_omni_client)
        response = app.submit_and_execute(principal="alice", capability="rag",
                                          action="query", arguments={"q": "hi"})
        self.assertEqual(self.workflows.get(response["job_id"])["status"], "completed")
        self.assertEqual(calls, [self.guard_service.url, self.capabilities["rag"].url])

    def test_denied_does_not_run_agent(self):
        calls = []
        def transport(url, payload):
            calls.append(url)
            return {"decision": "deny"}
        app = FoundationControlPlane(self.workflows, FoundationOrchestrator(
            self.guard_service, self.capabilities, transport=transport), self.agents, omni_guard_client=self.mock_omni_client)
        with self.assertRaises(IntegrationError):
            app.submit_and_execute(principal="alice", capability="rag", action="query", arguments={})
        self.assertEqual(calls, [self.guard_service.url])
