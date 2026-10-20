"""OmniGuard client for FoundationCentar-Next integration.

Provides a secure gateway to the OmniGuard Next central security boundary.
All tool execution requests must pass through this client for ALLOW/BLOCK
decisions. Fail-closed by default — gateway unavailability or errors
deny the operation, ensuring protected actions are never silently allowed.

NEVER embed default secrets. The OMNIGUARD_API_KEY must be provided
via a secure configuration source (CI secret, environment, or config file).
If the key is missing, the client must not start and must raise an error
rather than silently using a fallback credential.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Optional

import httpx
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OmniGuardDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass
class OmniGuardResult:
    decision: OmniGuardDecision
    confidence: float
    signature: str
    latency_ms: float
    tier_latencies: dict[str, float]
    blocked_reason: Optional[str] = None


class OmniGuardClient:
    """Client for OmniGuard gateway (http://localhost:8000/v1).

    Fail-closed design:
    - BLOCK decision → operation denied
    - Gateway unreachable → operation denied (not silently allowed)
    - Invalid credentials → operation denied (not silently allowed)
    - Malformed response → operation denied (not silently allowed)
    - Timeout → operation denied (not silently allowed)

    The local tool authorization below is an additional layer, NOT a
    bypass. OmniGuard gate must be the primary security boundary.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: Optional[str] = None,
        timeout: float = 15.0,
    ):
        """Initialize the OmniGuard client.

        Args:
            base_url: Gateway base URL (default: http://localhost:8000/v1)
            api_key: OmniGuard API key. Must be provided — no hardcoded fallback.
            timeout: Request timeout in seconds (default: 15.0, lower than default 30s
                     to fail fast on unresponsive gateways).
        """
        # --- REMOVED HARDCODED FALLBACK ---
        # api_key is now REQUIRED. If not provided via parameter and not found in
        # environment, raise ValueError immediately rather than silently using a
        # default credential that could grant unintended access.
        if api_key is not None:
            self.api_key = api_key
        else:
            # --- OMNIGUARD_API_KEY from environment ---
            env_key = os.environ.get("OMNIGUARD_API_KEY")
            if env_key is None:
                raise ValueError(
                    "OMNIGUARD_API_KEY not configured. "
                    "Provide api_key parameter or set OMNIGUARD_API_KEY environment variable."
                )
            self.api_key = env_key

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-API-Key": self.api_key},
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def inspect(
        self,
        messages: list[dict[str, Any]],
        model: str = "omniguard-2.0",
        metadata: Optional[dict[str, Any]] = None,
    ) -> OmniGuardResult:
        """Send messages to OmniGuard for inspection."""
        client = await self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "metadata": metadata or {},
        }
        try:
            resp = await client.post("/chat/completions", json=payload)
            decision_header = resp.headers.get("X-Governance-Decision", "BLOCK")
            decision = OmniGuardDecision(decision_header)
            return OmniGuardResult(
                decision=decision,
                confidence=float(resp.headers.get("X-Governance-Confidence", "0.0")),
                signature=resp.headers.get("X-Governance-Signature", ""),
                latency_ms=float(resp.headers.get("X-Inspection-Latency-Ms", "0.0")),
                tier_latencies={
                    "tier0": float(resp.headers.get("X-Tier0-Latency-Ms", "0.0")),
                    "tier1": float(resp.headers.get("X-Tier1-Latency-Ms", "0.0")),
                    "tier2": float(resp.headers.get("X-Tier2-Latency-Ms", "0.0")),
                    "tier3": float(resp.headers.get("X-Tier3-Latency-Ms", "0.0")),
                },
                blocked_reason=resp.json().get("detail") if decision == OmniGuardDecision.BLOCK else None,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="invalid_credentials",
                )
        except httpx.TimeoutException:
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_timeout",
            )
        except httpx.ConnectError as e:
            logger.warning("OmniGuard gateway connection failed: %s", str(e))
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_unreachable",
            )
        except httpx.HTTPError as e:
            # Unexpected HTTP error — fail-closed
            logger.warning("OmniGuard: HTTP error %s", str(e))
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="response_parse_error",
            )

    async def route(
        self,
        messages: list[dict[str, Any]],
        model: str = "omniguard-2.0",
        metadata: Optional[dict[str, Any]] = None,
    ) -> OmniGuardResult:
        """Route messages through OmniGuard gatekeeping.

        Returns an OmniGuardResult with the governance decision and metadata.
        Fail-closed: any error during routing defaults to BLOCK.
        """
        client = await self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "metadata": metadata or {},
        }
        try:
            resp = await client.post("/chat/completions", json=payload)
        except httpx.TimeoutException:
            logger.warning("OmniGuard gateway request timed out after %ss", self.timeout)
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_timeout",
            )
        except httpx.ConnectError as e:
            logger.warning("OmniGuard gateway connection failed: %s", str(e))
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_unreachable",
            )
        except httpx.HTTPError as e:
            logger.warning("OmniGuard: HTTP error %s", str(e))
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="response_parse_error",
            )

        # --- Process governance headers ---
        decision_header = resp.headers.get("X-Governance-Decision", None)
        if decision_header is None:
            # Missing governance header — fail-closed
            logger.warning(
                "OmniGuard response missing X-Governance-Decision header; body=%s",
                resp.text[:200],
            )
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="missing_governance_header",
            )

        # Parse the decision value
        try:
            decision = OmniGuardDecision(decision_header)
        except ValueError:
            # Invalid governance decision value — fail-closed
            logger.warning(
                "OmniGuard invalid X-Governance-Decision value: %s; body=%s",
                decision_header,
                resp.text[:200],
            )
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="invalid_governance_decision",
            )

        # Extract confidence if present
        try:
            confidence = float(resp.headers.get("X-Governance-Confidence", "0.0"))
        except (ValueError, TypeError):
            confidence = 0.0

        # Extract signature if present
        signature = resp.headers.get("X-Governance-Signature", "")

        # Extract tier latencies
        tier_latencies: dict[str, float] = {}
        for tier in ("tier0", "tier1", "tier2", "tier3"):
            try:
                tier_latencies[tier] = float(
                    resp.headers.get(f"X-{tier}-Latency-Ms", "0.0")
                )
            except (ValueError, TypeError):
                tier_latencies[tier] = 0.0

        # Parse body for additional blocked reason
        blocked_reason: Optional[str] = None
        try:
            body = resp.json()
            if decision == OmniGuardDecision.BLOCK:
                blocked_reason = body.get("detail")
        except (json.JSONDecodeError, KeyError):
            blocked_reason = None

        return OmniGuardResult(
            decision=decision,
            confidence=confidence,
            signature=signature,
            latency_ms=0.0,
            tier_latencies=tier_latencies,
            blocked_reason=blocked_reason,
        )
