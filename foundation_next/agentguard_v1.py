"""AgentGuard v1 execution client.

Unlike the legacy /toolcall adapter, /v1/execute executes the registered tool
inside AgentGuard. Never dispatch the same operation again from Foundation.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from foundation_next.orchestrator import IntegrationError


def _post_authenticated(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    if not url.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
        raise IntegrationError("AgentGuard endpoint must use HTTPS outside localhost")
    request = Request(
        url,
        data=json.dumps(payload, allow_nan=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            data = json.load(response)
    except Exception as exc:
        raise IntegrationError("AgentGuard execution request failed") from exc
    if not isinstance(data, dict):
        raise IntegrationError("Malformed AgentGuard response")
    return data


class AgentGuardV1Execution:
    """Authenticated, fail-closed client for the actual AgentGuard v1 API."""

    def __init__(
        self,
        endpoint: str,
        *,
        agent: str,
        api_key: str,
        transport: Callable[[str, dict[str, Any], str], dict[str, Any]] = _post_authenticated,
    ) -> None:
        if not endpoint.endswith("/v1/execute") or not agent or not api_key:
            raise ValueError("AgentGuard v1 endpoint, agent and API key required")
        if not endpoint.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
            raise ValueError("AgentGuard endpoint must use HTTPS outside localhost")
        self.endpoint, self.agent, self.api_key = endpoint, agent, api_key
        self.transport = transport

    def execute(
        self,
        *,
        capability: str,
        action: str,
        arguments: dict[str, Any],
        approval: str | None = None,
        request_id: str | None = None,
    ) -> Any:
        if not capability or not action or not isinstance(arguments, dict):
            raise ValueError("Invalid execution request")
        if approval is not None and (not isinstance(approval, str) or not approval):
            raise ValueError("Invalid approval token")
        identifier = request_id if request_id is not None else str(uuid4())
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 200:
            raise ValueError("Invalid request ID")
        payload = {
            "agent": self.agent,
            "tool": capability,
            "request_id": identifier,
            "payload": {"action": action, "arguments": arguments},
            "approval": approval,
        }
        try:
            response = self.transport(self.endpoint, payload, self.api_key)
        except IntegrationError:
            raise
        except Exception as exc:
            raise IntegrationError("AgentGuard execution request failed") from exc
        if (
            not isinstance(response, dict)
            or response.get("decision") != "ALLOW"
            or "result" not in response
        ):
            raise IntegrationError("AgentGuard execution not confirmed")
        return response["result"]
