"""Async MCP tool boundary: fail-closed OmniGuard inspection before dispatch."""
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .omniguard_client import OmniGuardClient, OmniGuardDecision


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str


class MCPGateway:
    def __init__(
        self,
        enable_omniguard: bool = True,
        *,
        omni_guard_client: OmniGuardClient | None = None,
    ):
        self._tools: dict[
            str, tuple[ToolSpec, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]]
        ] = {}
        self._enable_omniguard = enable_omniguard
        # The disabled path exists for legacy isolated unit tests only.
        # Production must construct the gateway with governance enabled.
        self._omniguard = (
            omni_guard_client or OmniGuardClient()
            if enable_omniguard
            else None
        )

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
        if self._enable_omniguard:
            if self._omniguard is None:
                raise ToolError("omniguard_not_configured")
            try:
                content = json.dumps(
                    {"tool": tool, "capability": capability, "arguments": arguments},
                    sort_keys=True,
                )
                result = await self._omniguard.inspect(
                    messages=[{"role": "user", "content": content}]
                )
                if result.decision != OmniGuardDecision.ALLOW:
                    raise ToolError("omniguard_not_allowed")
            except ToolError:
                raise
            except Exception as exc:
                raise ToolError("omniguard_inspection_failed") from exc

        if not authorization:
            raise ToolError("Missing authorization")
        entry = self._tools.get(tool)
        if entry is None or entry[0].capability != capability:
            raise ToolError("Tool is not registered for capability")
        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be an object")

        response = await entry[1](arguments)
        if not isinstance(response, dict) or response.get("status") != "success":
            raise ToolError("Tool did not confirm successful execution")
        return response

    async def health_check(self) -> bool:
        if not self._enable_omniguard or self._omniguard is None:
            return False
        try:
            result = await self._omniguard.inspect(
                messages=[{"role": "user", "content": "health_check"}]
            )
            return result.decision == OmniGuardDecision.ALLOW
        except Exception:
            return False
