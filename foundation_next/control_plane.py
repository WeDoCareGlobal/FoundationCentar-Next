"""FoundationCentar application service.

Jobs persist before execution. The security gate runs before any agent handler.
Identity must come from a trusted authenticated upstream; this module does
not implement authentication.

Integrated with OmniGuard for fail-closed governance enforcement.
OmniGuard ALLOW alone cannot bypass AgentGuard authorization.
Both approvals are required before any protected capability side effects.

CRITICAL: Missing or misconfigured OmniGuard gateway prevents ALL protected
execution. No fail-open behavior. OmniGuard is a mandatory governance layer.
"""
from typing import Any

import asyncio

from foundation_next.agents import AgentRegistry
from foundation_next.omniguard_client import OmniGuardClient, OmniGuardDecision
from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError
from foundation_next.workflows import WorkflowEngine


class FoundationControlPlane:
    def __init__(self, workflows: WorkflowEngine, guard: FoundationOrchestrator,
                 agents: AgentRegistry, *, omni_guard_client: OmniGuardClient):
        """
        Initialize with REQUIRED omni_guard_client — no default, no fallback.
        The client MUST be configured; otherwise protected execution cannot start.
        """
        if omni_guard_client is None:
            raise ValueError(
                "OmniGuardClient must be configured; cannot proceed without governance enforcement"
            )
        self.workflows = workflows
        self.guard = guard
        self.agents = agents
        self.omni_guard_client = omni_guard_client

    def submit_and_execute(self, *, principal: str, capability: str, action: str,
                             arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a protected capability through the dual-gate security framework.

        GATE 1: OmniGuard governance — ALLOW is mandatory. Any other decision,
        error, timeout, or connection failure BLOCKS execution entirely.

        GATE 2: AgentGuard authorization — ALLOW is mandatory after OmniGuard ALLOW.
        DENIED prevents execution.

        Only when BOTH gates approve does the protected capability execute
        (exactly one capability call with fully supplied arguments).
        """
        job_id = self.workflows.submit(principal=principal, capability=capability,
                                       action=action, arguments=arguments)

        def guarded_executor(capability: str, principal: str, action: str,
                             arguments: dict[str, Any]) -> dict[str, Any]:
            # GATE 1: OmniGuard enforcement — mandatory, fail-closed
            # No fallback, no skip. OmniGuard ALLOW is required.
            try:
                omni_result = asyncio.run(
                    self.omni_guard_client.inspect(
                        messages=[
                            {"role": "user", "content": f"execute {capability} "}
                        ]
                    )
                )
            except Exception as e:
                # Any OmniGuard error (timeout, connection failure, HTTP error,
                # malformed response, invalid payload) prevents execution.
                # CRITICAL: No fail-open — any error blocks.
                raise IntegrationError(
                    f"omniguard_execution_failed:{type(e).__name__}:{str(e)[:80]}"
                )

            # Verify OmniGuard decision is ALLOW — no other decision accepted
            if omni_result.decision != OmniGuardDecision.ALLOW:
                # BLOCK, DENY, or any other decision prevents execution
                raise IntegrationError(
                    f"omniguard_decision_{omni_result.decision.value if hasattr(omni_result.decision, 'value') else omni_result.decision}"
                )

            # Verify we have a valid block_reason if decision is BLOCK
            # (Should not reach here since decision != ALLOW would have raised,
            # but defensive check for malformed state)
            if hasattr(omni_result, 'blocked_reason') and omni_result.blocked_reason:
                pass  # available for logging/auditing if needed

            # GATE 2: AgentGuard enforcement — must also ALLOW
            # OmniGuard ALLOW alone cannot bypass AgentGuard authorization
            try:
                agent_result = self.guard.execute(
                    capability=capability,
                    principal=principal,
                    action=action,
                    arguments=arguments
                )
            except IntegrationError:
                # AgentGuard DENIED prevents execution
                raise IntegrationError("agentguard_denied")

            # Both OmniGuard ALLOW + AgentGuard ALLOWED: exactly one capability call
            # AgentResult should have status='success' from FoundationOrchestrator.execute()
            if not isinstance(agent_result, dict) or agent_result.get("status") != "success":
                raise IntegrationError("Capability execution not verified — result did not report success")
            return agent_result

        result = self.workflows.run(job_id, guarded_executor)
        return {"job_id": job_id, "result": result}
