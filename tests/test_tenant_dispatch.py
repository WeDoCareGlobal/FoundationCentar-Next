import unittest

from foundation_next.identity import AuthenticatedPrincipal, IdentityBoundary
from foundation_next.tenancy import TenantCatalog, ToolManifest
from foundation_next.tenant_dispatch import TenantDispatcher


class TenantDispatchTests(unittest.TestCase):
    def setUp(self):
        self.catalog = TenantCatalog()
        self.catalog.register(ToolManifest("tenant-a", "search", "1", "rag"))
        self.calls = []
        class Executor:
            def __init__(inner, calls):
                inner.calls = calls
            def execute(inner, **kwargs):
                inner.calls.append(kwargs)
                return {"status": "success"}
        self.dispatch = TenantDispatcher(IdentityBoundary("trusted-ingress"),
                                         self.catalog, Executor(self.calls))
        self.principal = AuthenticatedPrincipal("alice", "tenant-a", "trusted-ingress", True)

    def test_authorized_tenant_dispatch(self):
        result = self.dispatch.execute(principal=self.principal, tenant_id="tenant-a",
                                       tool="search", version="1", capability="rag",
                                       action="query", arguments={})
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(self.calls), 1)

    def test_cross_tenant_request_rejected_before_execution(self):
        with self.assertRaises(PermissionError):
            self.dispatch.execute(principal=self.principal, tenant_id="tenant-b",
                                  tool="search", version="1", capability="rag",
                                  action="query", arguments={})
        self.assertEqual(self.calls, [])

    def test_untrusted_issuer_rejected(self):
        principal = AuthenticatedPrincipal("alice", "tenant-a", "untrusted", True)
        with self.assertRaises(PermissionError):
            self.dispatch.execute(principal=principal, tenant_id="tenant-a",
                                  tool="search", version="1", capability="rag",
                                  action="query", arguments={})
        self.assertEqual(self.calls, [])

    def test_missing_tool_denied(self):
        with self.assertRaises(PermissionError):
            self.dispatch.execute(principal=self.principal, tenant_id="tenant-a",
                                  tool="unknown", version="1", capability="rag",
                                  action="query", arguments={})
        self.assertEqual(self.calls, [])
