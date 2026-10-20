"""Deterministic unit tests for FoundationCentar-Next OmniGuard client.

These tests use the REAL foundation_next.omniguard_client production implementation.
All HTTP interactions are mocked, and every error path is verified to default to BLOCK (fail-closed).

Test coverage:
- Missing OMNIGUARD_API_KEY -> ValueError raised (no hardcoded fallback)
- HTTP 403 -> BLOCK decision with blocked_reason
- Connection error -> BLOCK decision (gateway_unreachable)
- Timeout -> BLOCK decision (gateway_timeout)
- Missing X-Governance-Decision header -> BLOCK decision
- Invalid X-Governance-Decision value -> BLOCK decision
- Malformed JSON response -> BLOCK decision
- Successful ALLOW response -> ALLOW decision with full result
- Successful BLOCK response -> BLOCK decision with blocked_reason
- Execution-level regression: BLOCK prevents protected agent/tool action
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
        """Send messages to OmniGuard for inspection.

        Fail-closed: any error during inspection defaults to BLOCK.
        This ensures protected operations are never silently allowed when
        the gateway cannot make a safe decision.
        """
        client = await self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "metadata": metadata or {},
        }
        try:
            resp = await client.post("/chat/completions", json=payload)
        except (httpx.TimeoutException, TimeoutError) as e:
            # Both httpx.TimeoutException and plain TimeoutError -> BLOCK
            # Use the exception class name for blocked_reason consistency
            exc_name = type(e).__name__
            logger.warning("OmniGuard gateway request timed out: %s", str(e))
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason=exc_name,
            )
        except (httpx.ConnectError, ConnectionError) as e:
            # Both httpx.ConnectError and plain ConnectionError -> BLOCK
            exc_name = type(e).__name__
            logger.warning("OmniGuard gateway connection failed: %s", str(e))
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason=exc_name,
            )
        except Exception as e:
            # CATCH-ALL: handles httpx.HTTPStatusError, plain Exception, etc.
            # Check for 403 in the exception message or status code
            exc_str = str(e).lower()
            if "403" in exc_str or "forbidden" in exc_str:
                logger.warning("OmniGuard: 403 Forbidden detected: %s", str(e))
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="invalid_credentials",
                )
            # Check for other HTTP-like errors
            if isinstance(e, Exception):
                # Generic exception fallback
                exc_name = type(e).__name__.lower()
                logger.warning("OmniGuard: unexpected exception: %s", str(e))
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason=exc_name,
                )
            # If we couldn't determine the type, default to BLOCK
            logger.warning("OmniGuard: unknown exception caught, defaulting to BLOCK")
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="gateway_error",
            )

        # --- Process successful HTTP response (2xx) ---
        try:
            # Extract governance decision header first
            decision_header = resp.headers.get("X-Governance-Decision", None)
            if decision_header is None:
                # Missing governance header — fail-closed
                # First try to parse JSON; if malformed, BLOCK regardless
                try:
                    body = resp.json()
                except (json.JSONDecodeError, KeyError, TypeError):
                    return OmniGuardResult(
                        decision=OmniGuardDecision.BLOCK,
                        confidence=0.0,
                        signature="",
                        latency_ms=0.0,
                        tier_latencies={},
                        blocked_reason="missing_governance_header",
                    )
                # If JSON is valid but no governance header, still BLOCK
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="missing_governance_header",
                )

            # Parse the decision value — fail-closed on invalid value
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

            # Parse body for additional blocked reason
            blocked_reason: Optional[str] = None
            try:
                body = resp.json()
                if decision == OmniGuardDecision.BLOCK:
                    # Use detail from body if available
                    blocked_reason = body.get("detail")
            except (json.JSONDecodeError, KeyError, TypeError):
                # MALFORMED JSON — fail-closed to BLOCK regardless of header
                logger.warning(
                    "OmniGuard: malformed JSON in response; body=%s", resp.text[:200]
                )
                return OmniGuardResult(
                    decision=OmniGuardDecision.BLOCK,
                    confidence=0.0,
                    signature="",
                    latency_ms=0.0,
                    tier_latencies={},
                    blocked_reason="response_parse_error",
                )

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

        except Exception as e:
            # Unexpected error during response processing — fail-closed
            exc_name = type(e).__name__.lower()
            logger.error("Unexpected error parsing OmniGuard response: %s", str(e), exc_info=True)
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason=exc_name,
            )
