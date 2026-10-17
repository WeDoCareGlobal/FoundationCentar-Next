"""Adapter to the verified AgentGuard 0.2 /toolcall HTTP contract.

Source contract: POST /toolcall with agent, tool, input; response decision
ALLOWED/DENIED/APPROVAL_REQUIRED/RATE_LIMITED plus numeric audit_id.
An audit id is not a cryptographic authorization token. Deploy only across
an authenticated private service boundary.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from foundation_next.orchestrator import IntegrationError, post_json


class AgentGuardAdapter:
    def __init__(self, endpoint: str, *, agent: str,
                 transport: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json):
        if not endpoint.endswith("/toolcall") or not agent:
            raise ValueError("AgentGuard /toolcall endpoint and agent required")
        self.endpoint = endpoint
        self.agent = agent
        self.transport = transport

    def authorize(self, *, capability: str, action: str,
                  arguments: dict[str, Any]) -> dict[str, Any]:
        if not capability or not action or not isinstance(arguments, dict):
            raise ValueError("Invalid AgentGuard request")
        response = self.transport(self.endpoint, {
            "agent": self.agent,
            "tool": capability,
            "input": json.dumps({"action": action, "arguments": arguments}, sort_keys=True),
        })
        if not isinstance(response, dict):
            raise IntegrationError("AgentGuard returned malformed response")
        if response.get("decision") != "ALLOWED":
            raise IntegrationError("AgentGuard did not allow tool call")
        audit_id = response.get("audit_id")
        if type(audit_id) is not int or audit_id < 1:
            raise IntegrationError("AgentGuard did not return valid audit reference")
        return {"audit_id": audit_id, "decision": "ALLOWED"}
