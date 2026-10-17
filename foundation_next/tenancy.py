"""Foundation Next tenant-scoped tool catalog. No plaintext secrets stored."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolManifest:
    tenant_id: str
    name: str
    version: str
    capability: str
    enabled: bool = True


class TenantCatalog:
    def __init__(self):
        self._tools: dict[tuple[str, str, str], ToolManifest] = {}

    def register(self, manifest: ToolManifest) -> None:
        if not all((manifest.tenant_id, manifest.name, manifest.version, manifest.capability)):
            raise ValueError("Incomplete tool manifest")
        key = (manifest.tenant_id, manifest.name, manifest.version)
        if key in self._tools:
            raise ValueError("Tool version already registered")
        self._tools[key] = manifest

    def resolve(self, *, tenant_id: str, name: str, version: str,
                capability: str) -> ToolManifest:
        manifest = self._tools.get((tenant_id, name, version))
        if manifest is None or not manifest.enabled or manifest.capability != capability:
            raise PermissionError("Tool unavailable for tenant or capability")
        return manifest
