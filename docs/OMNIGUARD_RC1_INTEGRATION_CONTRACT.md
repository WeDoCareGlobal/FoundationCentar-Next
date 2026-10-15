# Enterprise AI OS RC1 — OmniGuard integration contract

Status: DRAFT. No runtime integration or passing tests are claimed.

## Architecture and boundaries

Client -> OmniGuard inspection -> FoundationCentar orchestration -> AgentGuard authorization -> tool executor.
AgentVault supplies scoped credentials, Hybrid RAG supplies ACL-filtered context, Agent Eval records outcomes. Never treat an OmniGuard ALLOW decision as tool execution authorization.

## Mandatory API contract (to implement and verify)

Request: request_id, tenant_id, principal_id, session_id, messages, tool_name, tool_arguments_digest, policy_version, timestamp.
Response: decision (ALLOW/BLOCK/REVIEW), decision_id, policy_version, reasons, expiry, signature. Verify signature with an appropriately managed secret and bind the decision to the request and tenant.

## Compatibility blocker

The FoundationCentar /toolcall and AgentGuard /v1/execute endpoints need a versioned, tested adapter. Do not silently assume the endpoint signatures match.

## Failures and approvals

- High-risk tool actions: fail closed if OmniGuard or AgentGuard cannot validate a decision.
- Read-only low-risk requests: degraded behavior only under explicitly approved, versioned policy.
- Approval must be verified server-side, tenant-bound, single-use where applicable and auditable.
- No credentials in source or sample production environment files.

## Acceptance tests

- ALLOW, BLOCK and REVIEW flows; prompt injection; missing/invalid signature; replay; cross-tenant request; unavailable gateway; expired approval; retries; audit delivery failure.
- CI executes live tests, not only cached benchmark reports.
- Trace identifiers propagate across services, with sensitive data redacted.

## Merge policy

Keep original main unchanged. Changes go through reviewable PRs after test evidence and human approval.
