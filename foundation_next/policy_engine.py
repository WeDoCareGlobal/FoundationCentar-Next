"""Foundation Next original policy evaluator.

Explicit deny wins. Empty allowlist denies by default. This local policy
layer supplements, never replaces, the external AgentGuard authorization gate.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    allowed_capabilities: frozenset[str]
    denied_capabilities: frozenset[str] = frozenset()
    require_approval: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def evaluate(policy: Policy, *, capability: str, approval_id: str | None = None) -> Decision:
    if not capability:
        return Decision(False, "missing_capability")
    if capability in policy.denied_capabilities:
        return Decision(False, "explicit_deny")
    if capability not in policy.allowed_capabilities:
        return Decision(False, "not_allowlisted")
    if capability in policy.require_approval and not approval_id:
        return Decision(False, "approval_required")
    return Decision(True, "policy_allow")
