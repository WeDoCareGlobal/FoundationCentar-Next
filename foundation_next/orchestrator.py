"""Fail-closed orchestration boundary for the FoundationCentar pre-publish system.

Integrates separately deployed AgentGuard and capability services over HTTP.
No simulated success: unavailable guard, malformed decisions, or failed tools raise.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen


class IntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Service:
    name: str
    url: str


def post_json(url: str, payload: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    if not url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
        raise IntegrationError("Remote services must use HTTPS")
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except Exception as exc:
        raise IntegrationError("Service request failed") from exc
    if not isinstance(result, dict):
        raise IntegrationError("Service response must be an object")
    return result


class FoundationOrchestrator:
    def __init__(
        self,
        guard: Service,
        capabilities: dict[str, Service],
        *,
        transport: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    ) -> None:
        if not capabilities:
            raise ValueError("At least one capability is required")
        self.guard = guard
        self.capabilities = dict(capabilities)
        self.transport = transport

    def execute(
        self,
        *,
        capability: str,
        principal: str,
        action: str,
        arguments: dict[str, Any],
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        if not principal or not action:
            raise ValueError("Principal and action are required")
        service = self.capabilities.get(capability)
        if service is None:
            raise IntegrationError("Capability not registered")
        decision = self.transport(self.guard.url, {
            "principal": principal,
            "capability": capability,
            "action": action,
            "arguments": arguments,
            "approval_id": approval_id,
        })
        # This is a provisional adapter contract, not a claim that an existing
        # AgentGuard deployment currently accepts this request format.
        if (
            decision.get("decision") != "allow"
            or not isinstance(decision.get("decision_id"), str)
            or not decision["decision_id"]
        ):
            raise IntegrationError("AgentGuard did not authorize execution")
        result = self.transport(service.url, {
            "principal": principal,
            "action": action,
            "arguments": arguments,
            "guard_decision_id": decision["decision_id"],
        })
        if result.get("status") != "success":
            raise IntegrationError("Capability execution was not successful")
        return result
