# FoundationCentar Next — source integration inventory (initial pass)

This is a first implementation slice, not a completed best-of consolidation.
All repositories below were inspected for their default-branch file trees via the connected GitHub account.

| Source | Candidate components | Integration status |
| --- | --- | --- |
| WeDoCareGlobal-CC/FoundationCentar | TypeScript backend, frontend, real-time subscribers | Identified; not ported |
| we-do-care-global/FoundationCentar | alternate Foundation frontend/backend | Identified; not ported |
| WeDoCareGlobal-CC/atlantida-os | Python orchestrator, skills, telemetry | Identified; simulator behavior needs replacement |
| WeDoCareGlobal-CC/gemini-mcp-agentic-tools | MCP server and Gemini client | Identified; authentication/isolation review pending |
| WeDoCareGlobal/agentguard-next | security and approval boundary | Provisional guarded integration interface added; contract compatibility unverified |
| WeDoCareGlobal-CC/agentvault | model adapters, vault and execution modules | Identified; identity and authorization remediation required |
| WeDoCareGlobal/agent-eval-next | evaluation and traces | Identified; contract and persistence pending |
| WeDoCareGlobal-CC/enterprise-hybrid-rag | retrieval API, hybrid search | Identified; vector fallback and evaluation integrity remediation required |

## Next integration gates

1. Audit full implementation files, branches, licenses and dependency graphs across accessible private/public repositories.
2. Define versioned service contracts; adapt actual AgentGuard API (current interface is provisional).
3. Port real orchestrator and state persistence, then wire authenticated MCP capabilities.
4. Add secure AgentVault, RAG and Agent Eval integrations with audit/event persistence.
5. Execute unit, integration, PostgreSQL and security suites in a reproducible CI environment.
6. Keep work private; require explicit approval for merges and publication.

No production deploy, existing repository replacement, or public release is authorized.
