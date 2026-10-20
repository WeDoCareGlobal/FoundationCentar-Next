"""Production-boundary regression tests for mandatory OmniGuard and AgentGuard."""
import asyncio
import json
import os
import tempfile
import unittest

import httpx

from foundation_next.agents import AgentRegistry, AgentSpec
from foundation_next.control_plane import FoundationControlPlane
from foundation_next.omniguard_client import (
    OmniGuardClient,
    OmniGuardDecision,
    OmniGuardResult,
)
from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError, Service
from foundation_next.workflows import WorkflowEngine


def decision(value):
    return OmniGuardResult(
        decision=value,
        confidence=1.0,
        signature="",
        latency_ms=0.0,
        tier_latencies={},
    )


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workflows = WorkflowEngine(os.path.join(self.tmp.name, "jobs.db"))
        self.agents = AgentRegistry()
        self.agents.register(
            AgentSpec("rag-agent", frozenset({"rag"})),
            lambda *_: {"status": "success"},
        )
        self.guard_service = Service("guard", "https://guard.example.test/check")
        self.capability_service = Service("rag", "https://rag.example.test/execute")
        self.capabilities = {"rag": self.capability_service}
        self.calls = []
        self.inspections = []
        self.omni = OmniGuardClient(base_url="http://localhost:8000/v1", api_key="test")
        self.omni_result = decision(OmniGuardDecision.ALLOW)

        async def inspect(messages=None, **kwargs):
            self.inspections.append(messages)
            if isinstance(self.omni_result, Exception):
                raise self.omni_result
            return self.omni_result

        self.omni.inspect = inspect
        self.agent_allowed = True

        def transport(url, payload):
            self.calls.append((url, payload))
            if url == self.guard_service.url:
                if self.agent_allowed:
                    return {"decision": "allow", "decision_id": "d-1"}
                return {"decision": "deny"}
            return {"status": "success", "answer": "retrieved"}

        self.transport = transport

    def tearDown(self):
        self.tmp.cleanup()

    def app(self, omni=None, agents=None):
        return FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=self.transport
            ),
            self.agents if agents is None else agents,
            omni_guard_client=self.omni if omni is None else omni,
        )

    def execute(self, app=None):
        return (app or self.app()).submit_and_execute(
            principal="alice",
            capability="rag",
            action="query",
            arguments={"q": "hi", "timeout": 30},
        )

    def assert_no_capability_calls(self):
        self.assertFalse(
            [url for url, _ in self.calls if url == self.capability_service.url]
        )

    def test_missing_omni_guard_rejected(self):
        with self.assertRaises(ValueError):
            FoundationControlPlane(
                self.workflows,
                FoundationOrchestrator(
                    self.guard_service, self.capabilities, transport=self.transport
                ),
                self.agents,
            )
        self.assert_no_capability_calls()

    def test_block_prevents_execution(self):
        self.omni_result = decision(OmniGuardDecision.BLOCK)
        with self.assertRaises(IntegrationError):
            self.execute()
        self.assertEqual(self.calls, [])
        self.assert_no_capability_calls()

    def test_timeout_returns_block(self):
        self.omni_result = asyncio.TimeoutError("private gateway detail")
        with self.assertRaisesRegex(IntegrationError, "^omniguard_inspection_failed$"):
            self.execute()
        self.assertEqual(self.calls, [])
        self.assert_no_capability_calls()

    def test_connection_error_returns_block(self):
        self.omni_result = httpx.ConnectError("private gateway detail")
        with self.assertRaisesRegex(IntegrationError, "^omniguard_inspection_failed$"):
            self.execute()
        self.assertEqual(self.calls, [])
        self.assert_no_capability_calls()

    def test_http_500_with_allow_header_returns_block(self):
        # Exercise real OmniGuardClient.inspect with an actual HTTP response.
        async def actual_inspect(messages=None, **kwargs):
            transport = httpx.MockTransport(
                lambda request: httpx.Response(
                    500,
                    headers={"X-Governance-Decision": "ALLOW"},
                    json={"error": "gateway unavailable"},
                )
            )
            async with httpx.AsyncClient(
                base_url="http://localhost:8000/v1", transport=transport
            ) as client:
                original = self.omni._client
                self.omni._client = client
                try:
                    return await OmniGuardClient.inspect(
                        self.omni, messages=messages, **kwargs
                    )
                finally:
                    self.omni._client = original

        self.omni.inspect = actual_inspect
        with self.assertRaises(IntegrationError):
            self.execute()
        self.assertEqual(self.calls, [])
        self.assert_no_capability_calls()

    def test_omniguard_allow_agentguard_denied(self):
        self.agent_allowed = False
        with self.assertRaises(IntegrationError):
            self.execute()
        self.assertEqual([url for url, _ in self.calls], [self.guard_service.url])
        self.assert_no_capability_calls()

    def test_omniguard_allow_agentguard_allowed(self):
        response = self.execute()
        self.assertEqual(self.workflows.get(response["job_id"])["status"], "completed")
        self.assertEqual(
            [url for url, _ in self.calls],
            [self.guard_service.url, self.capability_service.url],
        )
        self.assertEqual(self.calls[-1][1]["arguments"], {"q": "hi", "timeout": 30})

    def test_inspection_payload_contains_principal_capability_action_arguments(self):
        self.execute()
        self.assertEqual(len(self.inspections), 1)
        message = self.inspections[0][0]
        self.assertEqual(set(message), {"role", "content"})
        self.assertEqual(
            json.loads(message["content"]),
            {
                "principal": "alice",
                "capability": "rag",
                "action": "query",
                "arguments": {"q": "hi", "timeout": 30},
            },
        )

    def test_active_event_loop_no_bypass(self):
        async def inside_loop():
            with self.assertRaisesRegex(
                IntegrationError, "^omniguard_event_loop_unsupported$"
            ):
                self.execute()

        asyncio.run(inside_loop())
        self.assertEqual(self.calls, [])
        self.assert_no_capability_calls()

    def test_disabled_agent_prevents_capability_execution(self):
        disabled = AgentRegistry()
        disabled.register(
            AgentSpec("rag-agent", frozenset({"rag"}), enabled=False),
            lambda *_: {"status": "success"},
        )
        with self.assertRaisesRegex(IntegrationError, "^capability_not_available$"):
            self.execute(self.app(agents=disabled))
        self.assertEqual(self.calls, [])
        self.assert_no_capability_calls()


if __name__ == "__main__":
    unittest.main()
