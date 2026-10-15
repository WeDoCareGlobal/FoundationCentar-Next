# OmniGuard decision protocol v1 — proposed cross-repository contract

The legacy X-Governance-Signature cannot be used as authorization evidence: the signature payload is not exposed to the client and does not bind decision, tenant or request. Never accept legacy ALLOW as an authorization token.

## Canonical signed envelope

OmniGuard and FoundationCentar must agree on canonical serialization before activation. Use RFC 8785 JSON canonicalization (or a versioned deterministic binary encoding), authenticated with HMAC-SHA256 over the complete envelope excluding signature. A signing key must come from a secret manager, not source defaults.

Fields: protocol_version, request_id, tenant_id, principal_id, action, arguments_sha256, decision, issued_at, expires_at, nonce, policy_version, key_id. Sign every field. Reject missing, malformed or extra security-critical fields; reject mismatched request identity, tenant, principal, action and arguments digest; reject expired/future timestamps and replayed nonce. Constant-time signature comparison. A shared persistent replay store is required across gateway replicas.

ALLOW alone does not grant tool execution: AgentGuard must independently authorize the same tenant, principal, action and arguments. BLOCK and REVIEW must prevent execution.

## Migration gates

1. Implement v1 signing and verifier in isolated branches on both services.
2. Add positive and negative cross-service contract tests and tenant isolation tests.
3. Run the tests in CI with generated test-only keys and no production secrets.
4. Roll out to staging, verify audit persistence and failure behavior, then request human review.

Status: PROPOSED, not implemented or deployed. Legacy ALLOW intentionally fails closed on FoundationCentar RC1 branch.
