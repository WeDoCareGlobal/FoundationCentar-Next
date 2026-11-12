# Pre-Release Consolidation Baseline — FoundationCentar-Next

## Issue Reference
- Issue #2: "Pre-release: original-code consolidation and 10-step completion plan" (open)
- Acceptance: All required tests on exact candidate SHA; no mocked success, undocumented skipped integrations, exposed credentials, missing attribution, or unproven product claims. Preserve donor repositories; adapt selected modules on development branches. No public release or production deployment in this planning task. OmniGuard remains excluded.

## Baseline SHAs (from issue)
| Reference | SHA | Description |
|-----------|-----|-------------|
| Baseline | 8c63ff1 | Merge pull request #1 from WeDoCareGlobal/development/best-of-foundation-integration-20261014 |
| Current HEAD | b573c3d | docs: clarify engineering focus and evidence-based release status |

## Delta
- Commits ahead of baseline (8c63ff1): 70

## Step 1 Status: IN PROGRESS
**Task:** Zabilježiti baseline 8c63ff1, source manifest i postojeća 52 testa; zaključati opseg šest servisa i vlasništvo nad funkcijama.
(Document baseline, source manifest, existing 52 tests; lock scope of six services and function ownership.)

**Resolution plan:**
1. Document baseline 8c63ff1 as reviewed baseline
2. Create source manifest listing all modules and their origin
3. Document 52 passing unittest tests
4. Define six-service scope and function ownership matrix

## Source Selection (from issue)
| Source | Decision | Reason |
|--------|----------|--------|
| Original FoundationCentar/src/orchestrator.py | Adapt | Agent organization |
| Original atlantida-os/src/orchestrator.py | Adapt | Agent organization, but Worker.execute returns text |
| gemini-mcp-agentic-tools/server/mcp_server.py | Adapt | Real validated tools, but seed SQLite is demo |
| Original frontend/backend | Adapt | Requires AppDeploy dependency separation |
| agentguard_adapter.py | Keep | Sends /toolcall {agent,tool,input} |
| Next Guard | Adapt | Exposes /v1/execute with payload/request_id |
| SecuredControlPlane | Adapt | Intentionally rejects approval_verification_not_integrated |

## Steps 2–10
Documented in issue #2 body. Not started.

## Verification
- [ ] Baseline documented (this file)
- [ ] Step 1 source manifest and service scope documented
- [ ] Steps 2–10 not started
