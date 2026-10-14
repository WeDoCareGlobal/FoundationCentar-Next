"""Original capability-aware agent registry and deterministic routing."""
from dataclasses import dataclass
from typing import Any, Callable

class RoutingError(RuntimeError):
    pass

@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    capabilities: frozenset[str]
    enabled: bool = True

class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentSpec] = {}
        self._handlers: dict[str, Callable[[str, dict[str, Any]], dict[str, Any]]] = {}

    def register(self, spec: AgentSpec, handler: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        if not spec.agent_id or not spec.capabilities or spec.agent_id in self._agents:
            raise ValueError("Invalid or duplicate agent")
        self._agents[spec.agent_id] = spec
        self._handlers[spec.agent_id] = handler

    def resolve(self, capability: str) -> AgentSpec:
        candidates = sorted(
            (a for a in self._agents.values() if a.enabled and capability in a.capabilities),
            key=lambda a: a.agent_id,
        )
        if not candidates:
            raise RoutingError("No enabled agent supports requested capability")
        return candidates[0]

    def execute(self, capability: str, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        agent = self.resolve(capability)
        result = self._handlers[agent.agent_id](action, arguments)
        if not isinstance(result, dict) or result.get("status") != "success":
            raise RoutingError("Agent execution not confirmed")
        return {"agent_id": agent.agent_id, "result": result}
