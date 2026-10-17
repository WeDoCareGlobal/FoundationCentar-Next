# FoundationCentar — One-Click Agent Factory OS (Next Generation)

> **Status:** `v1.0.0-pre.1` — production-ready pre-release. The local (fail-open) orchestrator is fully operational. AgentGuard integration is wired but opt-in via `AGENTGUARD_ENABLED=true`.


[![CI](https://github.com/WeDoCareGlobal/FoundationCentar-Next/actions/workflows/ci.yml/badge.svg)](https://github.com/WeDoCareGlobal/FoundationCentar-Next/actions/workflows/ci.yml)
[![Release](https://github.com/WeDoCareGlobal/FoundationCentar-Next/actions/workflows/release.yml/badge.svg)](https://github.com/WeDoCareGlobal/FoundationCentar-Next/actions/workflows/release.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23073888.svg)](https://doi.org/10.5281/zenodo.23073888)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0009--8515--2727-green.svg)](https://orcid.org/0009-0009-8515-2727)
[![We Do Care Global](https://img.shields.io/badge/We%20Do%20Care%20Global-Enterprise%20AI%20Governance-purple.svg)](https://wedocare-global.com/)
[![Pre-release](https://img.shields.io/badge/release-1.0.0--pre.1-blue.svg)](https://github.com/WeDoCareGlobal/FoundationCentar-Next/releases/tag/v1.0.0-pre.1)

**Part of the [We Do Care Global](https://wedocare-global.com/) ecosystem — 6 published systems, Apache-2.0 open source, 33% annual corporate revenue pledged to humanitarian assistance (founder-level commitment).**

---

## Overview

**FoundationCentar-Next** is the next-generation **One-Click Agent Factory** — an autonomous cloud AI operating platform that orchestrates multi-agent workflows with human governance, bounded economics, and evidence-first verification.

**Status:** `v1.0.0-pre.1` — production-ready pre-release. The local (fail-open) orchestrator is fully operational. AgentGuard integration is wired but opt-in via `AGENTGUARD_ENABLED=true`.

> **Architecture**: Python (FastAPI orchestrator, NVIDIA NIM/vLLM model routing) + TypeScript (React control plane, AppDeploy backend, realtime WebSocket)

> **Merged from**: AtlanTida OS (Python orchestration) + We Do Care Global Agentic Operations OS (React/TypeScript control plane + AppDeploy backend)

---

## Polyglot Architecture

```
FoundationCentar-Next/
├── foundation_next/                 # Python: Orchestrator + Control Plane + Model Gateway
│   ├── orchestrator.py              # Fail-closed FoundationOrchestrator (AgentGuard-gated)
│   ├── local_orchestrator.py        # Fail-open Brain → Chiefs → Workers state machine
│   ├── local_skills.py              # Smart-meter diagnostic + half-hourly tariff skills
│   ├── control_plane/               # Governance, policy, agent registry
│   ├── agentguard_adapter.py        # AgentGuard integration
│   ├── policy_engine.py             # Policy-as-code evaluation
│   ├── retrieval/                   # Hybrid RAG integration
│   ├── mcp_gateway/                 # MCP server management
│   ├── models.yaml                  # Model registry: Chief→model (NIM + vLLM)
│   ├── main.py                      # CLI / Server / Daemon entry points (FastAPI)
│   └── __init__.py
├── frontend/                        # React + Vite + TypeScript (CEO Control Plane UI)
│   ├── src/App.tsx                  # CEO Dashboard: actions, approvals, missions, org, audit, learning
│   ├── src/main.tsx                 # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── postcss.config.js
├── backend/                         # TypeScript: AppDeploy SDK Backend (Control Plane API)
│   ├── index.ts                     # Control plane API: actions, approvals, OAuth, bridge, sync
│   ├── realtime-subscribers.ts      # WebSocket realtime updates
│   ├── package.json
│   └── tsconfig.json
├── config/                          # Configuration
│   └── integrations.example.json    # GitHub/ORCID/Zenodo + local AI bridge config
├── docs/                            # Architecture & operations docs
├── .zenodo.json                     # Zenodo metadata for DOI minting
├── CITATION.cff                     # Citation file format
├── Dockerfile                       # Multi-stage: frontend + backend + Python + nginx + supervisor
├── docker-compose.yml               # Full stack local dev
├── requirements.txt                 # fastapi, uvicorn, pydantic, httpx
├── pyproject.toml                   # Python package config
├── tests/                           # pytest suite for orchestrator + skills + ASGI entrypoint
└── .github/workflows/               # CI: lint, typecheck, test, docker build/push, Pages, Zenodo
```

---

## Quick Start

### Python Orchestrator (Core)
```bash
# Clone
git clone https://github.com/WeDoCareGlobal/FoundationCentar-Next.git
cd FoundationCentar-Next

# Install Python dependencies
pip install -r requirements.txt

# Run orchestrator API (port 8000)
uvicorn foundation_next.main:app --host 0.0.0.0 --port 8000

# Or use the CLI entry point
python -m foundation_next.main --mode server --port 8000

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/agents
curl http://localhost:8000/api/v1/skills

# Route a request through the Brain
curl -X POST http://localhost:8000/api/v1/brain/route \
  -H "Content-Type: application/json" \
  -d '{"domain": "operations", "action": "diagnose smart meter"}'

# Execute a skill
curl -X POST http://localhost:8000/api/v1/execute-skill \
  -H "Content-Type: application/json" \
  -d '{"prompt": "smart_meter_diagnostic", "domain": "operations"}'
```

### Full Stack (Docker Compose - Production Ready)
```bash
# Build and run full stack (frontend + python API + nginx + optional agentguard + vllm)
docker-compose up -d

# Frontend: http://localhost:8080
# Python API: http://localhost:8080/api/python/*
# Health: http://localhost:8080/health
```

### With AgentGuard (fail-closed security gate)

```bash
AGENTGUARD_ENABLED=true \
AGENTGUARD_URL=http://localhost:8000 \
docker-compose up -d
```

### Frontend Development (React)
```bash
cd frontend
npm install
npm run dev  # Vite dev server on :5173
```

### Backend Development (TypeScript)
```bash
cd backend
npm install
npm run dev  # ts-node on :3001
```

---

## Model Registry (`models.yaml`)

Maps each Chief/Worker role to **primary + fallback** model endpoints (OpenAI-compatible):

| Role | Primary | Fallback |
|------|---------|----------|
| **Brain** (Global Router) | NVIDIA NIM: `nemotron-3-ultra-550b` | NIM: `nemotron-3-super-120b` → vLLM: `Qwen3-235B-A22B` |
| **Chief Operations** | vLLM: `Qwen-AgentWorld-35B-A3B` | vLLM: `Qwen3-30B` → NIM: `nemotron-70b` |
| **Chief DevOps** | vLLM: `Qwen3-Coder-32B` | vLLM: `Qwen2.5-Coder-32B` → NIM: `codestral-22b` |
| **Chief Research** | vLLM: `Qwen3-30B-A3B-Thinking` | NIM: `nemotron-3-ultra` → NIM: `nemotron-3-super` |
| **Chief Finance/Legal** | NIM: `llama-3.1-405b` | NIM: `nemotron-70b` → vLLM: `Qwen3-32B` |
| **Chief Marketing/Sales** | vLLM: `Qwen3-32B` | NIM: `mistral-large-2` |
| **Workers (default)** | vLLM: `Qwen3-14B` | vLLM: `Mixtral-8x22B` → NIM: `mixtral-8x22b` |

> **vLLM ports**: 8001–8013 (see `models.yaml:vllm_ports`) — deploy via `docker-compose.yml`

---

## CEO Control Plane (Frontend)

The React dashboard (`frontend/src/App.tsx`) provides:

| Tab | Purpose |
|-----|---------|
| **Dashboard** | KPI metrics (verified revenue, tracked cost, profit, bound budgets), running missions, org chart, governance |
| **Missions** | List all missions with status, cost/budget, verification |
| **Org Chart** | Human CEO → AI Lead → 4 Department Leads → Workers |
| **Timeline** | Workflow execution timeline |
| **Learning** | Optimization versions, scores, optimization notes |
| **Audit** | Append-only ledger: actions, decisions, costs, outcomes |

### CEO Actions (One-Click)
- **Start Research** — Regulatory & Knowledge mission
- **Start Workflow** — Product & Engineering mission
- **Execute Mission** — Operations & Finance mission
- **Approve / Reject** — Governance decisions on proposals
- **Pause / Resume** — Execution control
- **Expand Team** — Capability-gap → Agent Spec → sandbox → promotion
- **Learn & Optimize** — Rebalance routing, verifier thresholds
- **Retire Agent** — Safe decommissioning after reassignment
- **Emergency Stop** — Halt all execution, preserve state

---

## Backend API (AppDeploy SDK)

TypeScript backend (`backend/index.ts`) exposes:

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/control-plane` | ✓ | Full state: missions, approvals, audit, learning, agents |
| `GET /api/integrations` | ✓ | GitHub/ORCID/Zenodo connection status |
| `POST /api/integrations/:provider/start` | ✓ | OAuth flow start (GitHub/ORCID/Zenodo) |
| `GET /api/oauth/:provider/callback` | — | OAuth callback, encrypts & stores tokens |
| `DELETE /api/integrations/:provider` | ✓ | Disconnect provider |
| `POST /api/actions` | ✓ | CEO actions (research/workflow/execute/expand/retire/learn/stop/pause/resume) |
| `POST /api/approvals/decision` | ✓ | Approve/reject pending proposals |
| `GET /api/bridge/config` | — | Local AI bridge protocol spec |
| `POST /api/bridge/receipt` | ✓ | Receive worker receipt from local runtime |
| `GET /api/sync/status` | ✓ | GitHub/Zenodo/ORCID sync status |
| `POST /api/sync/run` | ✓ | Trigger unified account sync |
| `WS /api/realtime/subscribe` | — | Realtime entity updates |

---

## Unified Identity

- **Google** = Primary AppDeploy identity (CEO)
- **GitHub/ORCID/Zenodo** = OAuth connections linked to same AppDeploy user ID
- **Secrets required**: `APP_ENCRYPTION_KEY`, `GITHUB_CLIENT_ID/SECRET`, `ORCID_CLIENT_ID/SECRET`, `ZENODO_CLIENT_ID/SECRET`
- **Tokens** encrypted server-side (AES-256-GCM) before persistence; browser sees only connection status

---

## AgentGuard Integration

FoundationCentar-Next integrates **AgentGuard** (`WeDoCareGlobal/agentguard-next`) as the security control plane:
- Policy evaluation for every tool call
- Per-agent rate limiting
- HMAC-chained audit log
- Human-in-the-loop approvals
- Kill-switch coordination

AgentGuard is **opt-in** — set `AGENTGUARD_ENABLED=true` and provide `AGENTGUARD_URL`. When disabled (default), execution runs locally (fail-open) for standalone operation.

```python
# foundation_next/agentguard_adapter.py
from agentguard import Guard, create_app

guard = Guard(policy_path="policy.yaml")
app = create_app(guard, api_key="...", admin_key="...")
```

---

## Deployment

| Target | Command |
|--------|---------|
| **Docker Compose (local)** | `docker-compose up -d` |
| **GHCR** | `ghcr.io/WeDoCareGlobal/FoundationCentar-Next` (auto on push to `main`) |
| **Cloud** | Requires Cloudflare API token + secrets |

### CI/CD (`.github/workflows/`)
- `ci.yml` — Lint, typecheck, test, security scan on PR/push
- `release.yml` — Version bump, tag, Docker build/push on release
- `docker.yml` — Multi-arch build/push to GHCR on `main` push
- `pages.yml` — Deploy `docs/` to GitHub Pages
- `zenodo.yml` — Archive releases to Zenodo, mint DOI, push to ORCID

---

## License

Apache-2.0 — see [LICENSE](LICENSE) / [LICENSE-OS](LICENSE-OS) for details.

---

## Citation

```bibtex
@software{perla2026foundationcentar,
  author = {Perla, Emir and We Do Care Global},
  title = {FoundationCentar — One-Click Agent Factory OS},
  version = {1.0.0-pre.1},
  year = {2026},
  doi = {10.5281/zenodo.23073888},
  url = {https://github.com/WeDoCareGlobal/FoundationCentar-Next}
}
```

---

## WDCG Ecosystem

| System | Repo | Purpose |
|--------|------|---------|
| **AgentGuard** | `WeDoCareGlobal/agentguard-next` | Security & governance control plane |
| **FoundationCentar** | `WeDoCareGlobal/FoundationCentar-Next` | **This repo** — One-Click Agent Factory |
| **Enterprise Hybrid-RAG** | `WeDoCareGlobal/enterprise-hybrid-rag-next` | Hybrid retrieval |
| **Agent Eval** | `WeDoCareGlobal/agent-eval-next` | Evaluation harness |
| **AgentVault** | `WeDoCareGlobal/AgentVault-Next` | Tool registry & assurance |
| **Pharma Intelligence OS** | `WeDoCareGlobal/Pharma-Intelligence-Os-Next` | Regulatory intelligence |