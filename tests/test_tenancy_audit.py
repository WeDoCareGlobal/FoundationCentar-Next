import unittest
from foundation_next.tenancy import TenantCatalog, ToolManifest
from foundation_next.audit_chain import AuditChain


class TenancyAuditTests(unittest.TestCase):
    def test_tenant_isolation(self):
        catalog = TenantCatalog()
        catalog.register(ToolManifest("tenant-a", "search", "1", "rag"))
        self.assertEqual(catalog.resolve(tenant_id="tenant-a", name="search", version="1", capability="rag").name, "search")
        with self.assertRaises(PermissionError):
            catalog.resolve(tenant_id="tenant-b", name="search", version="1", capability="rag")

    def test_wrong_capability_denied(self):
        catalog = TenantCatalog()
        catalog.register(ToolManifest("tenant-a", "search", "1", "rag"))
        with self.assertRaises(PermissionError):
            catalog.resolve(tenant_id="tenant-a", name="search", version="1", capability="deploy")

    def test_duplicate_version_rejected(self):
        catalog = TenantCatalog()
        manifest = ToolManifest("tenant-a", "search", "1", "rag")
        catalog.register(manifest)
        with self.assertRaises(ValueError):
            catalog.register(manifest)

    def test_audit_chain_detects_modified_event(self):
        chain = AuditChain()
        chain.append({"action": "search", "status": "ok"})
        chain.append({"action": "evaluate", "status": "ok"})
        self.assertTrue(chain.verify())
        chain.records[0].event["status"] = "altered"
        self.assertFalse(chain.verify())

    def test_audit_chain_detects_removed_middle_record(self):
        chain = AuditChain()
        chain.append({"action": "a"})
        chain.append({"action": "b"})
        chain.append({"action": "c"})
        del chain.records[1]
        self.assertFalse(chain.verify())
