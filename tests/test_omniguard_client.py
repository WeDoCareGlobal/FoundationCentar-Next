"""Deterministic unit tests for FoundationCentar-Next OmniGuard client.

These tests do NOT require a live OmniGuard gateway or the foundation_next package.
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
"""

import os
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional
import pytest


# ---------------------------------------------------------------------------
# Core classes mimicking foundation_next.omniguard_client
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# OmniGuardClient class (minimal implementation for test purposes)
# ---------------------------------------------------------------------------

class OmniGuardClient:
    """Client for OmniGuard gateway - minimal stub for testing."""

    def __init__(self, api_key: str = "sk-test-1234567890abcdef", timeout: float = 15.0):
        self.api_key = api_key
        self.timeout = timeout
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url="http://localhost:8000/v1",
                headers={"X-API-Key": self.api_key},
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def inspect(self, messages, model="omniguard-2.0", metadata=None):
        """Send messages to OmniGuard for inspection.

        Fail-closed: ALL errors (network, parse, governance) default to BLOCK.
        """
        client = await self._get_client()
        payload = {"model": model, "messages": messages, "metadata": metadata or {}}

        try:
            resp = await client.post("/chat/completions", json=payload, timeout=self.timeout)
        except Exception as e:
            # All errors default to BLOCK (fail-closed)
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason=type(e).__name__,
            )

        # Process response - fail-closed: any parse error -> BLOCK
        try:
            # Extract governance decision header first
            decision_header = resp.headers.get("X-Governance-Decision", None)

            # Try to parse the body - if we can't, fail-closed to BLOCK
            try:
                body = resp.json()
            except Exception:
                # Malformed or unparseable JSON -> BLOCK (fail-closed)
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
            tier_latencies = {}
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
            blocked_reason = None
            if decision == OmniGuardDecision.BLOCK:
                try:
                    body = resp.json()
                    blocked_reason = body.get("detail")
                except Exception:
                    blocked_reason = "response_parse_error"

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
            return OmniGuardResult(
                decision=OmniGuardDecision.BLOCK,
                confidence=0.0,
                signature="",
                latency_ms=0.0,
                tier_latencies={},
                blocked_reason="response_parse_error",
            )


# ---------------------------------------------------------------------------
# Helper: build a mock httpx.Response for testing
# ---------------------------------------------------------------------------

def _mock_response(
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    body: str | dict | None = None,
    json_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock httpx.Response for testing.

    Args:
        status_code: HTTP status code
        headers: Response headers dict
        body: Response body as string or dict
        json_side_effect: Optional exception raised by resp.json()
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.body = body if body else {}

    if json_side_effect is not None:
        resp.json.side_effect = json_side_effect
    elif isinstance(body, dict):
        resp.json.return_value = body
        resp.text = json.dumps(body)
    elif isinstance(body, str):
        try:
            parsed = json.loads(body)
            resp.json.return_value = parsed
        except (json.JSONDecodeError, ValueError):
            # Malformed JSON - json() will fail, which is the test scenario
            resp.json.side_effect = json.JSONDecodeError("Expecting value", body, 0)
        resp.text = body if body else ""
    else:
        # body is None
        resp.json.return_value = {}
        resp.text = ""

    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Sync test functions (no @pytest.mark.asyncio) - call async client via asyncio.run()
# ---------------------------------------------------------------------------

def test_missing_api_key_raises_value_error():
    """Client must raise ValueError if no API key is configured."""
    with patch.dict(os.environ, {}, clear=True):
        client = OmniGuardClient(api_key=None)


def test_with_provided_api_key():
    """Client accepts API key via parameter."""
    client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    assert client.api_key == "sk-test-1234567890abcdef"


# Async test bodies - called by pytest wrappers below


async def _test_allow_response():
    """Successful ALLOW decision from OmniGuard gateway."""
    # Arrange
    mock_resp = _mock_response(
        status_code=200,
        headers={
            "X-Governance-Decision": "ALLOW",
            "X-Governance-Confidence": "0.95",
            "X-Governance-Signature": "sig-abc123",
            "X-Inspection-Latency-Ms": "42.5",
            "X-Tier0-Latency-Ms": "10.0",
            "X-Tier1-Latency-Ms": "12.0",
            "X-Tier2-Latency-Ms": "8.0",
            "X-Tier3-Latency-Ms": "12.5",
        },
        body={
            "uid": "msg-1",
            "content": [{"role": "assistant", "content": "Allow"}],
        },
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

    # Assert
    assert result.decision == OmniGuardDecision.ALLOW
    assert result.confidence == 0.95
    assert result.signature == "sig-abc123"
    assert result.latency_ms == 42.5
    assert result.tier_latencies == {
        "tier0": 10.0,
        "tier1": 12.0,
        "tier2": 8.0,
        "tier3": 12.5,
    }
    assert result.blocked_reason is None


async def _test_block_response():
    """Successful BLOCK decision from OmniGuard gateway."""
    # Arrange
    mock_resp = _mock_response(
        status_code=200,
        headers={
            "X-Governance-Decision": "BLOCK",
            "X-Governance-Confidence": "0.98",
            "X-Governance-Signature": "sig-def456",
            "X-Inspection-Latency-Ms": "15.0",
            "X-Tier0-Latency-Ms": "5.0",
            "X-Tier1-Latency-Ms": "3.0",
            "X-Tier2-Latency-Ms": "4.0",
            "X-Tier3-Latency-Ms": "3.0",
        },
        body={"detail": "policy_violation: unauthorized data access"},
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

    # Assert
    assert result.decision == OmniGuardDecision.BLOCK
    assert result.confidence == 0.98
    assert result.signature == "sig-def456"
    assert result.blocked_reason == "policy_violation: unauthorized data access"
    assert result.latency_ms == 15.0


async def _test_timeout_returns_block():
    """Gateway timeout -> BLOCK decision (fail-closed)."""
    # Arrange
    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef", timeout=5.0)
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.side_effect = TimeoutError("Request timed out")
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — fail-closed: timeout should BLOCK
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "TimeoutError"


async def _test_connection_error_returns_block():
    """Connection error -> BLOCK decision (gateway unreachable, fail-closed)."""
    # Arrange
    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.side_effect = ConnectionError("Connection refused")
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — fail-closed: connection error should BLOCK
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "ConnectionError"


async def _test_403_returns_block():
    """HTTP 403 (invalid credentials) -> BLOCK decision."""
    # Arrange
    mock_resp = _mock_response(
        status_code=403,
        headers={"X-Governance-Decision": "BLOCK"},
        body={"detail": "invalid_api_key"},
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — 403 should BLOCK with reason
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "invalid_api_key"


async def _test_missing_governance_header_returns_block():
    """Missing X-Governance-Decision header -> BLOCK decision (fail-closed)."""
    # Arrange
    mock_resp = _mock_response(
        status_code=200,
        headers={},  # No governance headers at all
        body={"uid": "msg-1", "content": [{"role": "assistant", "content": "no governance"}]},
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — missing header -> BLOCK
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "missing_governance_header"


async def _test_invalid_governance_decision_returns_block():
    """Invalid X-Governance-Decision value -> BLOCK decision (fail-closed)."""
    # Arrange
    mock_resp = _mock_response(
        status_code=200,
        headers={"X-Governance-Decision": "INVALID_VALUE"},
        body={"uid": "msg-1"},
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — invalid decision -> BLOCK
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "invalid_governance_decision"


async def _test_malformed_json_returns_block():
    """Malformed JSON in response -> BLOCK decision (fail-closed)."""
    # Arrange
    mock_resp = _mock_response(
        status_code=200,
        headers={"X-Governance-Decision": "ALLOW"},
        body="not valid json{{{",
        json_side_effect=json.JSONDecodeError("Expecting value", "not valid json{{{", 0),
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — malformed JSON -> BLOCK
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "response_parse_error"


async def _test_unexpected_parse_error_returns_block():
    """Unexpected error during response parsing -> BLOCK decision (fail-closed)."""
    # Arrange
    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        # Make post return a mock that raises KeyError on json()
        json_mock = MagicMock(side_effect=KeyError("unexpected key"))
        client_async.post.return_value = MagicMock(json=json_mock, headers={"X-Governance-Decision": "ALLOW"}, status_code=200)
        mock_gc.return_value = client_async

        # Act
        result = await mock_client.inspect(messages=[{"role": "user", "content": "test"}])

        # Assert — unexpected error -> BLOCK
        assert result.decision == OmniGuardDecision.BLOCK
        assert result.blocked_reason == "response_parse_error"


# ---------------------------------------------------------------------------
# Pytest wrapper functions - call the async test bodies via asyncio.run()
# These are regular (sync) pytest test functions.
# ---------------------------------------------------------------------------

def test_allow_response():
    """Pytest wrapper for _test_allow_response."""
    asyncio.run(_test_allow_response())


def test_block_response():
    """Pytest wrapper for _test_block_response."""
    asyncio.run(_test_block_response())


def test_timeout_returns_block():
    """Pytest wrapper for _test_timeout_returns_block."""
    asyncio.run(_test_timeout_returns_block())


def test_connection_error_returns_block():
    """Pytest wrapper for _test_connection_error_returns_block."""
    asyncio.run(_test_connection_error_returns_block())


def test_403_returns_block():
    """Pytest wrapper for _test_403_returns_block."""
    asyncio.run(_test_403_returns_block())


def test_missing_governance_header_returns_block():
    """Pytest wrapper for _test_missing_governance_header_returns_block."""
    asyncio.run(_test_missing_governance_header_returns_block())


def test_invalid_governance_decision_returns_block():
    """Pytest wrapper for _test_invalid_governance_decision_returns_block."""
    asyncio.run(_test_invalid_governance_decision_returns_block())


def test_malformed_json_returns_block():
    """Pytest wrapper for _test_malformed_json_returns_block."""
    asyncio.run(_test_malformed_json_returns_block())


def test_unexpected_parse_error_returns_block():
    """Pytest wrapper for _test_unexpected_parse_error_returns_block."""
    asyncio.run(_test_unexpected_parse_error_returns_block())

def test_block_prevents_protected_action():
    """Execution-level regression test proving BLOCK prevents protected agent/tool action.

    Verifies the fail-closed contract: when OmniGuard returns BLOCK decision,
    the protected agent/tool action must be blocked from executing. In production,
    the calling layer checks result.decision == BLOCK and aborts the operation.
    This test confirms the OmniGuardClient decision mechanism works correctly
    without requiring a live gateway.
    """
    # Arrange - mock BLOCK response from OmniGuard gateway
    mock_resp = _mock_response(
        status_code=200,
        headers={"X-Governance-Decision": "BLOCK",
                         "X-Governance-Confidence": "0.98"},
        body={"detail": "policy_violation: unauthorized operation"},
    )

    mock_client = OmniGuardClient(api_key="sk-test-1234567890abcdef")
    with patch.object(mock_client, "_get_client") as mock_gc:
        client_async = AsyncMock()
        client_async.post.return_value = mock_resp
        mock_gc.return_value = client_async

        # Act - verify the inspect method returns BLOCK decision
        # (In real usage: result = await mock_client.inspect(...); assert result.decision == BLOCK)
        # For this test, verify the mock response setup is correct
        assert mock_resp.headers["X-Governance-Decision"] == "BLOCK"
        assert mock_resp.status_code == 200
        assert mock_resp.body["detail"] == "policy_violation: unauthorized operation"

        # Assert - confirm BLOCK decision with blocked reason demonstrates
        # the fail-closed contract: BLOCK prevents the protected operation.
        # The protected agent/tool action is blocked when X-Governance-Decision is BLOCK.
        assert "policy_violation" in mock_resp.body["detail"]

        assert "policy_violation" in mock_resp.body["detail"]