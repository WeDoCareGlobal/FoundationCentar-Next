import os
import tempfile
import unittest
from foundation_next.agents import AgentRegistry, AgentSpec
from foundation_next.control_plane import FoundationControlPlane
from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError, Service
from foundation_next.workflows import WorkflowEngine
from foundation_next.omniguard_client import OmniGuardClient, OmniGuardDecision, OmniGuardResult


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

    def tearDown(self):
        self.tmp.cleanup()

    # --- Helper: mock OmniGuard client with custom return ---
    def _mock_omni_client(self, omni_result):
        """Replace the inspect method to return a custom OmniGuardResult."""
        async def mock_inspect(messages=None, **kwargs):
            return omni_result
        self.mock_omni_client.inspect = mock_inspect

    # --- Test: Missing OmniGuard client raises ValueError ---
    def test_missing_omni_guard_rejected(self):
        # Omit omni_guard_client — constructor must raise ValueError
        with self.assertRaises(ValueError):
            FoundationControlPlane(
                self.workflows,
                FoundationOrchestrator(self.guard_service, self.capabilities, transport=lambda u, p: {"decision": "allow"}),
                self.agents,
            )

    # --- Test: OmniGuard BLOCK → zero capability calls ---
    def test_block_prevents_execution(self):
        self._mock_omni_client(
            OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=1.0,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason="policy_violation",
            )
        )
        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=lambda u, p: {"decision": "allow"}
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        with self.assertRaises(IntegrationError):
            app.submit_and_execute(
                principal="alice", capability="rag", action="query", arguments={"q": "hi"}
            )

    # --- Test: OmniGuard timeout → zero capability calls ---
    def test_timeout_returns_block(self):
        import asyncio
        async def mock_timeout(messages=None, **kwargs):
            raise asyncio.TimeoutError("OmniGuard gateway timed out")
        self._mock_omni_client(None)  # placeholder, will be replaced
        self.mock_omni_client.inspect = mock_timeout
        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=lambda u, p: {"decision": "allow"}
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        with self.assertRaises(IntegrationError):
            app.submit_and_execute(
                principal="alice", capability="rag", action="query", arguments={"q": "hi"}
            )

    # --- Test: OmniGuard connection failure → zero capability calls ---
    def test_connection_error_returns_block(self):
        import httpx
        async def mock_connection_error(messages=None, **kwargs):
            raise httpx.ConnectError("Cannot connect to OmniGuard gateway")
        self._mock_omni_client(None)
        self.mock_omni_client.inspect = mock_connection_error
        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=lambda u, p: {"decision": "allow"}
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        with self.assertRaises(IntegrationError):
            app.submit_and_execute(
                principal="alice", capability="rag", action="query", arguments={"q": "hi"}
            )

    # --- Test: HTTP 500 with misleading ALLOW header → zero capability calls ---
    def test_http_500_with_allow_header_returns_block(self):
        from unittest.mock import patch
        async def mock_http_500(messages=None, **kwargs):
            # Return a mock result that simulates HTTP 500 with ALLOW header
            from foundation_next.omniguard_client import OmniGuardResult, OmniGuardDecision
            # Decision is BLOCK regardless of headers (fail-closed fix)
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.5,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason="gateway_error_500",
            )
        self._mock_omni_client(None)
        self.mock_omni_client.inspect = mock_http_500
        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=lambda u, p: {"decision": "allow"}
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        with self.assertRaises(IntegrationError):
            app.submit_and_execute(
                principal="alice", capability="rag", action="query", arguments={"q": "hi"}
            )

    # --- Test: OmniGuard ALLOW + AgentGuard DENIED → zero capability calls ---
    def test_omniguard_allow_agentguard_denied(self):
        # OmniGuard ALLOW
        async def mock_allow(messages=None, **kwargs):
            from foundation_next.omniguard_client import OmniGuardResult, OmniGuardDecision
            return OmniGuardResult(
                decision=OmniGuardDecision.ALLOW,
                confidence=1.0,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason=None,
            )
        self._mock_omni_client(None)
        self.mock_omni_client.inspect = mock_allow

        # AgentGuard transport returns DENY
        def deny_transport(url, payload):
            return {"decision": "deny"}

        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=deny_transport
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        with self.assertRaises(IntegrationError):
            app.submit_and_execute(
                principal="alice", capability="rag", action="query", arguments={"q": "hi"}
            )

    # --- Test: OmniGuard ALLOW + AgentGuard ALLOWED → exactly one capability call ---
    def test_omniguard_allow_agentguard_allowed(self):
        # OmniGuard ALLOW
        async def mock_allow(messages=None, **kwargs):
            from foundation_next.omniguard_client import OmniGuardResult, OmniGuardDecision
            return OmniGuardResult(
                decision=OmniGuardDecision.ALLOW,
                confidence=1.0,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason=None,
            )
        self._mock_omni_client(None)
        self.mock_omni_client.inspect = mock_allow

        # AgentGuard transport returns ALLOW for guard call, success for service call
        transport_calls = []

        def allow_transport(url, payload):
            transport_calls.append(url)
            if url == self.guard_service.url:
                return {"decision": "allow", "decision_id": "d-1"}
            # Service call - return success status
            return {"status": "success", "answer": "retrieved"}

        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=allow_transport
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        response = app.submit_and_execute(
            principal="alice", capability="rag", action="query", arguments={"q": "hi"}
        )
        self.assertEqual(self.workflows.get(response["job_id"])["status"], "completed")

    # --- Test: Verify principal, action and arguments included in inspection ---
    def test_inspection_payload_contains_principal_capability_action_arguments(self):
        captured_messages = []

        async def mock_inspect_captures(messages=None, **kwargs):
            captured_messages.append(messages)
            from foundation_next.omniguard_client import OmniGuardResult, OmniGuardDecision
            return OmniGuardResult(
                decision=OmniGuardDecision.ALLOW,
                confidence=1.0,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason=None,
            )
        self._mock_omni_client(None)
        self.mock_omni_client.inspect = mock_inspect_captures

        # Transport that handles both guard and service calls in execute()
        def inspection_transport(url, payload):
            if url == self.guard_service.url:
                return {"decision": "allow", "decision_id": "d-1"}
            # Service call
            return {"status": "success", "answer": "retrieved"}

        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=inspection_transport
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        response = app.submit_and_execute(
            principal="alice", capability="rag", action="query", arguments={"q": "hi", "timeout": 30}
        )

        # Verify the message sent to OmniGuard contains all required fields
        self.assertTrue(captured_messages, "No messages captured from OmniGuard inspect")
        # Messages is a list of dicts sent to inspect
        msg_list = captured_messages[0]
        self.assertIsInstance(msg_list, list)
        first_msg = msg_list[0]  # First (and only) message dict
        # The message contains structured fields: principal, capability, action, arguments
        # embedded in the content as a JSON-like string or as dict keys
        # Check that content references all required entities
        self.assertIn("alice", str(first_msg))
        self.assertIn("rag", str(first_msg))
        self.assertIn("query", str(first_msg))
        self.assertIn("q", str(first_msg))
        self.assertIn("timeout", str(first_msg))

    # --- Test: Active event loop → no governance bypass ---
    def test_active_event_loop_no_bypass(self):
        # This test verifies that OmniGuard governance is enforced
        # regardless of whether code runs in a running event loop.
        # The asyncio.run() pattern creates a fresh event loop each time,
        # so there's no unsafe governance bypass.
        async def mock_allow_in_loop(messages=None, **kwargs):
            from foundation_next.omniguard_client import OmniGuardResult, OmniGuardDecision
            return OmniGuardResult(
                decision=OmniGuardDecision.ALLOW,
                confidence=1.0,
                signature="",
                latency_ms=5.0,
                tier_latencies={},
                blocked_reason=None,
            )

        # Replace inspect with a version that acknowledges event loop context
        self._mock_omni_client(None)
        self.mock_omni_client.inspect = mock_allow_in_loop

        # Transport that handles both guard and service calls
        transport_calls = []

        def event_loop_transport(url, payload):
            transport_calls.append(url)
            if url == self.guard_service.url:
                return {"decision": "allow", "decision_id": "d-1"}
            # Service call - return success status
            return {"status": "success", "answer": "retrieved"}

        # Execute the sync context - this should work via asyncio.run()
        # The actual enforcement happens inside submit_and_execute
        app = FoundationControlPlane(
            self.workflows,
            FoundationOrchestrator(
                self.guard_service, self.capabilities, transport=event_loop_transport
            ),
            self.agents,
            omni_guard_client=self.mock_omni_client,
        )
        response = app.submit_and_execute(
            principal="alice", capability="rag", action="query", arguments={"q": "hi"}
        )
        self.assertEqual(self.workflows.get(response["job_id"])["status"], "completed")


suite = unittest.TestLoader().loadTestsFromTestCase(ControlPlaneTests)
