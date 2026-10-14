import unittest
from foundation_next.tenancy import TenantCatalog, ToolManifest


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
