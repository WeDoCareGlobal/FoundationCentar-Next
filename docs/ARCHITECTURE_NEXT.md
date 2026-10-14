# FoundationCentar Next — original pre-publish architecture

## Design decision

This is a newly written implementation informed by audit findings from the owner's repositories.
It does **not** copy or wholesale migrate source code from existing repositories.

- `foundation_next/workflows.py`: original SQLite-backed durable job state and append-only event history.
- `foundation_next/orchestrator.py`: guarded capability execution interface; guard protocol is provisional.
- Capabilities: explicit allowlisted service registry, rather than synthetic agent responses.
- Planned adapters: real AgentGuard authorization, AgentVault secret broker, MCP tool gateway, RAG retrieval, Agent Eval trace/quality checks.
- No claims of deployment, authentication, multi-worker locking, signed audit, or production readiness.

## Known limitations

SQLite engine is a single-process starting point; crash recovery, leases, cancellation, idempotency, authorization, migrations and PostgreSQL are pending. External guard authorization contract is not yet integrated with the actual AgentGuard service. The current orchestrator passes a caller-supplied principal; authenticated identity binding is a required next step.

## Pre-publish acceptance

Real tool execution with verified identities; fail-closed guard; durable retries and recovery; no fabricated metrics; tested external contracts; security review; private release candidate and human approval before publication.
