"""Local policy-gated workflow dispatch.

This wrapper applies local policy before the existing external authorization
boundary. An approval id is only a reference: the external guard must validate
its authenticity and scope.
"""
from typing import Any

from foundation_next.control_plane import FoundationControlPlane
from foundation_next.policy_engine import Policy, evaluate


class PolicyDenied(RuntimeError):
    pass


class SecuredControlPlane:
    def __init__(self, application: FoundationControlPlane, policy: Policy):
        self.application = application
        self.policy = policy

    def execute(self, *, principal: str, capability: str, action: str,
                arguments: dict[str, Any], approval_id: str | None = None) -> dict[str, Any]:
        decision = evaluate(self.policy, capability=capability, approval_id=approval_id)
        if not decision.allowed:
            raise PolicyDenied(decision.reason)
        # The existing control plane does not forward approval_id; approval-
        # requiring capabilities remain blocked until the full verification
        # contract is wired end-to-end.
        if capability in self.policy.require_approval:
            raise PolicyDenied("approval_verification_not_integrated")
        return self.application.submit_and_execute(
            principal=principal, capability=capability,
            action=action, arguments=arguments,
        )
