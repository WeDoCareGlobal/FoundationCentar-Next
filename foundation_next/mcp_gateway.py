"""MCP tool dispatch boundary. Only explicitly registered tools can execute."""
from dataclasses import dataclass
from typing import Any, Callable


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str


class MCPGateway:
    def __init__(self):
        self._tools: dict[str, tuple[ToolSpec, Callable[[dict[str, Any]], dict[str, Any]]]] = {}

    def register(self, spec: ToolSpec, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        if not spec.name or not spec.capability or spec.name in self._tools:
            raise ValueError("Invalid or duplicate tool")
        self._tools[spec.name] = (spec, handler)

    def execute(self, *, tool: str, capability: str, arguments: dict[str, Any],
                authorization: str) -> dict[str, Any]:
        if not authorization:
            raise ToolError("Missing authorization")
        entry = self._tools.get(tool)
        if entry is None or entry[0].capability != capability:
            raise ToolError("Tool is not registered for capability")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        result = entry[1](arguments)
        if not isinstance(result, dict) or result.get("status") != "success":
            raise ToolError("Tool did not confirm successful execution")
        return result
