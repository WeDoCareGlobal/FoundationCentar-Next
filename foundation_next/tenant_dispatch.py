"""Tenant-aware dispatch combining identity, catalog and guarded execution.

Authentication proof must be verified by a separate trusted ingress before
AuthenticatedPrincipal is constructed. Never construct it from request JSON.
"""
from typing import Any

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    tenant_id: str
    issuer: str
    authenticated: bool

    def __post_init__(self):
        if not self.subject or not self.tenant_id or not self.issuer or not self.authenticated:
            raise ValueError("Invalid principal")


class IdentityBoundary:
    def __init__(self, trusted_issuer: str):
        if not trusted_issuer:
            raise ValueError("Trusted issuer required")
        self.trusted_issuer = trusted_issuer

    def validate(self, principal: AuthenticatedPrincipal, *, tenant_id: str) -> None:
        if not isinstance(principal, AuthenticatedPrincipal):
            raise PermissionError("Principal required")
        if principal.issuer != self.trusted_issuer or principal.tenant_id != tenant_id:
            raise PermissionError("Issuer or tenant mismatch")
from foundation_next.tenancy import TenantCatalog
from foundation_next.agentguard_execution import GuardedExecution


class TenantDispatcher:
    def __init__(self, identity: IdentityBoundary, catalog: TenantCatalog,
                 executor: GuardedExecution):
        self.identity = identity
        self.catalog = catalog
        self.executor = executor

    def execute(self, *, principal: AuthenticatedPrincipal, tenant_id: str,
                tool: str, version: str, capability: str, action: str,
                arguments: dict[str, Any]) -> dict[str, Any]:
        self.identity.validate(principal, tenant_id=tenant_id)
        self.catalog.resolve(tenant_id=tenant_id, name=tool,
                             version=version, capability=capability)
        return self.executor.execute(principal=principal.subject,
                                     capability=capability, action=action,
                                     arguments=arguments)
