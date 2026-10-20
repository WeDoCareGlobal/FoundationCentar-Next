"""Fail-closed FoundationCentar control plane with OmniGuard and AgentGuard gates."""
import asyncio
import json
from typing import Any

from foundation_next.agents import AgentRegistry
from foundation_next.omniguard_client import OmniGuardClient, OmniGuardDecision
from foundation_next.orchestrator import FoundationOrchestrator, IntegrationError
from foundation_next.workflows import WorkflowEngine


class FoundationControlPlane:
    def __init__(
        self,
        workflows: WorkflowEngine,
        guard: FoundationOrchestrator,
        agents: AgentRegistry,
        *,
        omni_guard_client: OmniGuardClient | None = None,
    ):
        if omni_guard_client is None:
            raise ValueError("OmniGuardClient is required for protected execution")
        self.workflows = workflows
        self.guard = guard
        self.agents = agents
        self.omni_guard_client = omni_guard_client

    def submit_and_execute(
        self,
        *,
        principal: str,
        capability: str,
        action: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        job_id = self.workflows.submit(
            principal=principal,
            capability=capability,
            action=action,
            arguments=arguments,
        )

        def guarded_executor(
            capability: str,
            principal: str,
            action: str,
            arguments: dict[str, Any],
        ) -> dict[str, Any]:
            # A synchronous entry point cannot call asyncio.run inside an active loop.
            # Reject safely rather than silently skipping governance.
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                raise IntegrationError("omniguard_event_loop_unsupported")

            # The gateway's chat/completions schema guarantees processing of
            # message.content; arbitrary additional message keys may be ignored.
            # Keep request context in deterministic JSON content for inspection.
            context = json.dumps(
                {
                    "principal": principal,
                    "capability": capability,
                    "action": action,
                    "arguments": arguments,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            try:
                result = asyncio.run(
                    self.omni_guard_client.inspect(
                        messages=[{"role": "user", "content": context}]
                    )
                )
                decision = result.decision
            except Exception as exc:
                raise IntegrationError("omniguard_inspection_failed") from exc
            if decision != OmniGuardDecision.ALLOW:
                raise IntegrationError("omniguard_not_allowed")

            # Registry validation is distinct from remote AgentGuard authorization.
            # Never dispatch an unregistered or disabled capability.
            try:
                self.agents.resolve(capability)
            except Exception as exc:
                raise IntegrationError("capability_not_available") from exc

            try:
                response = self.guard.execute(
                    capability=capability,
                    principal=principal,
                    action=action,
                    arguments=arguments,
                )
            except IntegrationError as exc:
                raise IntegrationError("agentguard_denied") from exc
            if not isinstance(response, dict) or response.get("status") != "success":
                raise IntegrationError("capability_execution_unverified")
            return response

        result = self.workflows.run(job_id, guarded_executor)
        return {"job_id": job_id, "result": result}
