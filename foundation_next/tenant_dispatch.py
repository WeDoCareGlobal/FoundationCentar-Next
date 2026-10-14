"""Tenant-aware dispatch combining identity, catalog and guarded execution.

Authentication proof must be verified by a separate trusted ingress before
AuthenticatedPrincipal is constructed. Never construct it from request JSON.
"""
from typing import Any

from foundation_next.identity import AuthenticatedPrincipal, IdentityBoundary
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
