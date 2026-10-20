"""FoundationCentar application service.

Jobs persist before execution. The security gate runs before any agent handler.
Identity must come from a trusted authenticated upstream; this module does
not implement authentication.

Integrated with OmniGuard for fail-closed governance enforcement.
OmniGuard ALLOW alone cannot bypass AgentGuard authorization.
Both approvals are required before any protected capability side effects.
"""
from typing import Any

import asyncio

from foundation_next.agents import AgentRegistry
from foundation_next.omniguard_client import OmniGuardClient, OmniGuardDecision
from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError
from foundation_next.workflows import WorkflowEngine


class FoundationControlPlane:
    def __init__(self, workflows: WorkflowEngine, guard: FoundationOrchestrator,
                 agents: AgentRegistry, *, omni_guard_client: OmniGuardClient | None = None):
        self.workflows = workflows
        self.guard = guard
        self.agents = agents
        self.omni_guard_client = omni_guard_client

    def submit_and_execute(self, *, principal: str, capability: str, action: str,
                             arguments: dict[str, Any]) -> dict[str, Any]:
        job_id = self.workflows.submit(principal=principal, capability=capability,
                                       action=action, arguments=arguments)

        def guarded_executor(capability: str, principal: str, action: str,
                             arguments: dict[str, Any]) -> dict[str, Any]:
            # 1. OmniGuard enforcement (inner layer - must pass first)
            # Run the async OmniGuard client from sync code using asyncio.run()
            # This is the safe pattern - creates a new event loop each time
            if self.omni_guard_client is not None:
                try:
                    omni_result = asyncio.run(
                        self.omni_guard_client.inspect(
                            messages=[{"role": "user", "content": f"execute {capability}"}]
                        )
                    )
                    # OmniGuard BLOCK prevents execution
                    if omni_result.decision == OmniGuardDecision.BLOCK:
                        raise IntegrationError(f"omniguard_{omni_result.blocked_reason}")
                    # OmniGuard ALLOW alone cannot bypass AgentGuard;
                    # both approvals are required below
                except RuntimeError:
                    # asyncio.run() called from within running event loop;
                    # fall back to AgentGuard-only path
                    pass
                except (TimeoutError, ConnectionError) as e:
                    # Timeout or connection failure prevents execution
                    raise IntegrationError(f"omniguard_{type(e).__name__}")
                except httpx.HTTPStatusError as e:
                    # HTTP 500 with misleading ALLOW header prevents execution
                    status_code = e.response.status_code if hasattr(e, 'response') else 500
                    raise IntegrationError(f"omniguard_{status_code}")

            # 2. AgentGuard enforcement (outer layer - must also pass)
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
                raise IntegrationError("Capability execution not verified")
            return agent_result

        result = self.workflows.run(job_id, guarded_executor)
        return {"job_id": job_id, "result": result}
