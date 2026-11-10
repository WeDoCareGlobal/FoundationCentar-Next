# FoundationCentar — One-Click Agent Factory OS

[![CI](https://github.com/WeDoCareGlobal/FoundationCentar-Next/actions/workflows/ci.yml/badge.svg)](https://github.com/WeDoCareGlobal/FoundationCentar-Next/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0009--8515--2727-green.svg)](https://orcid.org/0009-0009-8515-2727)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22945778.svg)](https://doi.org/10.5281/zenodo.22945778)
[![We Do Care Global](https://img.shields.io/badge/We%20Do%20Care%20Global-Enterprise%20AI%20Governance-purple.svg)](https://wedocare-global.com/)

**FoundationCentar** is a production-grade, 24/7 autonomous cloud AI operating platform — a **One-Click Agent Factory** that orchestrates multi-agent workflows with human governance, bounded economics, and evidence-first verification.

> **Merged from**: AtlanTida OS (Python/FastAPI orchestration) + We Do Care Global Agentic Operations OS (React/TypeScript control plane + AppDeploy backend)

Part of the [We Do Care Global](https://wedocare-global.com/) ecosystem — 6 published systems, Apache-2.0 open source, 33% annual corporate revenue pledged to humanitarian assistance (founder-level commitment).

## System Architecture

### Authority Hierarchy

```
Human CEO → AI Lead → Team Leads (Chiefs) → Workers → Verifier → Outcome → Learning
```

### Core Loops

| Loop | Flow |
|---|---|
| **Economic** | Mission → Budget → Execution → Cost → Evidence → Verification → Revenue/Outcome → Learning |
| **Local AI** | Cloud Control Plane → Mission Package → Local AI Runtime → Worker Execution → Receipt → Verifier → Control Plane |
| **Research/Release** | GitHub commit → GitHub release → Zenodo archive/DOI |

## Unified Repository Structure

```
FoundationCentar/
├── src/                          # Python: Orchestrator + FastAPI Telemetry
├── frontend/                     # React + Vite + TypeScript (Control Plane UI)
├── backend/                      # TypeScript: AppDeploy SDK backend
├── config/                       # Configuration
├── docs/                         # Architecture & operations docs
├── models.yaml                   # Model registry
├── cron.json                     # Scheduled sync
├── .zenodo.json                  # Zenodo metadata for DOI minting
├── CITATION.cff                  # Citation file format
├── Dockerfile                    # Multi-stage build
├── requirements.txt              # Python dependencies
└── .github/workflows/            # CI: validate, release, docker build/push to GHCR
```

## Quickstart

### Local Development (Python API only)

```bash
git clone https://github.com/WeDoCareGlobal/FoundationCentar-Next.git
cd FoundationCentar-Next
pip install -r requirements.txt
python src/main.py --mode server
curl http://localhost:8000/health
```

## Metadata

- License: Apache 2.0
- ORCID: 0009-0009-8515-2727
- Citation: see `CITATION.cff`
- Zenodo archive: `.zenodo.json`
- Version: 1.0.0

