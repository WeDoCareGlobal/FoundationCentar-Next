"""OmniGuard client for FoundationCentar-Next integration.

Fail-closed: ALL error paths (timeout, connection failure, 403, missing headers,
malformed responses) default to BLOCK — never allow protected operations when
the gateway is unavailable or misconfigured.

Authentication: OMNIGUARD_API_KEY must be provided via environment variable or
constructor parameter. No hardcoded fallback credentials.
"""

from __future__ import annotations

import os
import json
import httpx
import logging
from typing import Any, Optional
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
    """Client for OmniGuard gateway with fail-closed security.

    Fail-closed principle: ALL error paths default to BLOCK, preventing
    protected agent/tool execution when the gateway is unavailable or
    misconfigured.

    Authentication: OMNIGUARD_API_KEY must be provided via secure configuration.
    ValueError raised if not configured (no hardcoded fallback credentials).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: Optional[str] = None,
        timeout: float = 15.0,
    ):
        # Prefer environment variable; fall back to constructor parameter
        self.api_key = api_key or os.environ.get("OMNIGUARD_API_KEY")
        if not self.api_key:
            raise ValueError("OMNIGUARD_API_KEY not configured")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

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

    async def inspect(self, messages: list[dict[str, str]], model: str = "omniguard-2.0", metadata: dict[str, Any] | None = None) -> OmniGuardResult:
        """Send messages to OmniGuard for inspection.

        Fail-closed: ANY error (network, parse, governance) defaults to BLOCK.
        This ensures protected operations are never silently allowed when
        the gateway cannot make a safe decision.
        """
        client = await self._get_client()
        payload = {"model": model, "messages": messages, "metadata": metadata or {}}

        try:
            resp = await client.post("/chat/completions", json=payload, timeout=self.timeout)
        except httpx.TimeoutException:
            # Gateway timeout -> BLOCK (fail-closed)
            logger.warning("OmniGuard: gateway timeout")
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_timeout",
            )
        except httpx.ConnectError:
            # Connection error -> BLOCK (gateway unreachable, fail-closed)
            logger.warning("OmniGuard: gateway unreachable (connection error)")
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_unreachable",
            )
        except httpx.HTTPStatusError as e:
            # HTTP error (e.g., 403 invalid credentials) - re-raise to be handled
            raise
        except Exception as e:
            # Other network error -> BLOCK (fail-closed)
            logger.warning(f"OmniGuard: network error: {type(e).__name__}")
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason=type(e).__name__,
            )

        try:
            # Extract governance decision header first
            decision_header = resp.headers.get("X-Governance-Decision", None)

            # Try to parse the body - if we can't, fail-closed to BLOCK
            try:
                body = resp.json()
            except Exception:
                # Malformed or unparseable JSON -> BLOCK (fail-closed)
                logger.warning("OmniGuard: malformed JSON response")
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="response_parse_error",
                )

            # Now process the decision header with body available
            if decision_header is None:
                # Missing governance header -> BLOCK (fail-closed)
                logger.warning("OmniGuard: missing X-Governance-Decision header")
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="missing_governance_header",
                )

            try:
                decision = OmniGuardDecision(decision_header)
            except ValueError:
                # Invalid governance decision value -> BLOCK (fail-closed)
                logger.warning(f"OmniGuard: invalid governance decision: {decision_header}")
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="invalid_governance_decision",
                )

            # Extract confidence
            try:
                confidence = float(resp.headers.get("X-Governance-Confidence", "0.0"))
            except (ValueError, TypeError):
                confidence = 0.0

            # Extract signature
            signature = resp.headers.get("X-Governance-Signature", "")

            # Extract tier latencies (case-insensitive lookup)
            tier_latencies: dict[str, float] = {}
            for tier in ("tier0", "tier1", "tier2", "tier3"):
                # Try exact match first (e.g., X-tier0-Latency-Ms)
                value = resp.headers.get(f"X-{tier}-Latency-Ms", None)
                if value is None:
                    # Try title-cased version (e.g., X-Tier0-Latency-Ms)
                    value = resp.headers.get(f"X-{tier.title()}-Latency-Ms", None)
                if value is None:
                    value = "0.0"
                try:
                    tier_latencies[tier] = float(value)
                except (ValueError, TypeError):
                    tier_latencies[tier] = 0.0

            # Blocked reason from body (if BLOCK decision)
            blocked_reason: Optional[str] = None
            if decision == OmniGuardDecision.BLOCK:
                blocked_reason = body.get("detail")

            # Inspection latency
            latency_ms = 0.0
            try:
                latency_ms = float(resp.headers.get("X-Inspection-Latency-Ms", "0.0"))
            except (ValueError, TypeError):
                latency_ms = 0.0

            return OmniGuardResult(
                decision=decision,
                confidence=confidence,
                signature=signature,
                latency_ms=latency_ms,
                tier_latencies=tier_latencies,
                blocked_reason=blocked_reason,
            )

        except Exception:
            # Any unexpected error during response processing -> BLOCK (fail-closed)
            logger.warning("OmniGuard: unexpected error during response processing")
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="response_parse_error",
            )
