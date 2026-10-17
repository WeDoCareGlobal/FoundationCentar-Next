"""MCP tool dispatch boundary with OmniGuard integration. Only explicitly registered tools can execute."""
from __future__ import annotations
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .omniguard_client import OmniGuardDecision, OmniGuardResult, get_omniguard_client


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str


class MCPGateway:
    def __init__(self, enable_omniguard: bool = True):
        self._tools: dict[str, tuple[ToolSpec, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]]] = {}
        self._enable_omniguard = enable_omniguard
        self._omniguard = get_omniguard_client() if enable_omniguard else None

    def register(
        self,
        spec: ToolSpec,
        handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        if not spec.name or not spec.capability or spec.name in self._tools:
            raise ValueError("Invalid or duplicate tool")
        self._tools[spec.name] = (spec, handler)

    async def execute(
        self,
        *,
        tool: str,
        capability: str,
        arguments: dict[str, Any],
        authorization: str,
    ) -> dict[str, Any]:
        # 1. OmniGuard inspection (if enabled)
        if self._enable_omniguard and self._omniguard:
            # Build messages from tool call for inspection
            messages = [
                {"role": "system", "content": "Tool call inspection"},
                {
                    "role": "user",
                    "content": f"Tool: {tool}, Capability: {capability}, Arguments: {arguments}",
                },
            ]
            result: OmniGuardResult = await self._omniguard.inspect(messages)
            if result.decision == OmniGuardDecision.BLOCK:
                raise ToolError(
                    f"OmniGuard blocked tool call: {result.blocked_reason or 'policy violation'}"
                )

        # 2. Local tool authorization
        if not authorization:
            raise ToolError("Missing authorization")
        entry = self._tools.get(tool)
        if entry is None or entry[0].capability != capability:
            raise ToolError("Tool is not registered for capability")
        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be an object")

        # 3. Execute tool
        result = await entry[1](arguments)
        if not isinstance(result, dict) or result.get("status") != "success":
            raise ToolError("Tool did not confirm successful execution")
        return result

    async def health_check(self) -> bool:
        """Check health of OmniGuard gateway."""
        if not self._enable_omniguard or not self._omniguard:
            return True
        return await self._omniguard.health_check()
