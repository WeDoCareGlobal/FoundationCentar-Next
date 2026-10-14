"""Execution bridge using AgentGuard's actual /toolcall contract.

The upstream principal must be authenticated. An audit reference is retained
for traceability, not treated as an independently verifiable permission token.
"""
from typing import Any, Callable

from foundation_next.agentguard_adapter import AgentGuardAdapter
from foundation_next.orchestrator import IntegrationError


class GuardedExecution:
    def __init__(self, guard: AgentGuardAdapter,
                 capabilities: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]):
        self.guard = guard
        self.capabilities = dict(capabilities)

    def execute(self, *, principal: str, capability: str, action: str,
                arguments: dict[str, Any]) -> dict[str, Any]:
        if not principal or capability not in self.capabilities:
            raise IntegrationError("Missing principal or unknown capability")
        decision = self.guard.authorize(capability=capability, action=action,
                                        arguments=arguments)
        result = self.capabilities[capability]({
            "principal": principal, "action": action, "arguments": arguments,
            "guard_audit_id": decision["audit_id"],
        })
        if not isinstance(result, dict) or result.get("status") != "success":
            raise IntegrationError("Capability execution not confirmed")
        return result
