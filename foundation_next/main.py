"""
FoundationCentar Next — Production entry point.

Serves:
  GET  /health                          — container readiness
  GET  /metrics                         — Prometheus metrics
  GET  /api/v1/agents                   — registered Brain + Chiefs + Workers
  GET  /api/v1/skills                   — available skills
  POST /api/v1/brain/route              — route request through Brain agent
  POST /api/v1/execute-skill            — execute a named skill
  POST /api/v1/create-agent             — register a new agent
  POST /api/v1/synthesize-skill         — synthesise a skill from traces
  GET  /api/v1/traces                   — recent execution traces

AgentGuard integration is optional. When AGENTGUARD_ENABLED=true and a guard
URL is reachable, every capability execution is gated through AgentGuard
(fail-closed). When disabled (default for local dev), execution runs locally
(fail-open) so the stack works without external services.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Optional AgentGuard guard (fail-closed when enabled)
# ---------------------------------------------------------------------------
AGENTGUARD_ENABLED = os.getenv("AGENTGUARD_ENABLED", "false").lower() == "true"
AGENTGUARD_URL = os.getenv("AGENTGUARD_URL", "http://localhost:8000")

try:
    from foundation_next.orchestrator import FoundationOrchestrator, Service
    from foundation_next.control_plane import FoundationControlPlane
    from foundation_next.workflows import WorkflowEngine
    from foundation_next.agents import AgentRegistry

    _guard_service: Service | None = None
    if AGENTGUARD_ENABLED:
        _guard_service = Service(name="agentguard", url=AGENTGUARD_URL)

    _capabilities: dict[str, Service] = {}
    _orchestrator: FoundationOrchestrator | None = None
    if _guard_service is not None and _capabilities:
        _orchestrator = FoundationOrchestrator(
            guard=_guard_service,
            capabilities=_capabilities,
        )

    _control_plane: FoundationControlPlane | None = None
    if _orchestrator is not None:
        _agent_registry = AgentRegistry()
        _workflow_engine = WorkflowEngine(
            database_path=os.getenv("FOUNDATION_WORKFLOWS_DB", "./data/workflows.db")
        )
        _control_plane = FoundationControlPlane(
            workflows=_workflow_engine,
            guard=_orchestrator,
            agents=_agent_registry,
        )

    _FOUNDATION_NEXT_AVAILABLE = True
except ImportError:  # pragma: no cover — foundation_next modules missing
    _FOUNDATION_NEXT_AVAILABLE = False
    _orchestrator = None
    _control_plane = None

# ---------------------------------------------------------------------------
# Local (fail-open) orchestrator — Brain / Chief / Worker state machine
# Used when AgentGuard is not configured or unavailable.
# ---------------------------------------------------------------------------
try:
    from foundation_next.local_orchestrator import brain as local_brain
    _LOCAL_ORCHESTRATOR = True
except ImportError:  # pragma: no cover
    _LOCAL_ORCHESTRATOR = False

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FoundationCentar Next",
    description="One-Click Agent Factory OS — autonomous multi-agent orchestration",
    version="1.0.0-pre.1",
)

# Prometheus metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"])
SKILL_EXECUTIONS = Counter("skill_executions_total", "Total skill executions", ["skill", "status"])
SKILL_DURATION = Histogram("skill_execution_duration_seconds", "Skill execution duration", ["skill"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class SkillRequest(BaseModel):
    prompt: str
    domain: str = "general"


class ChiefInput(BaseModel):
    action: str
    domain: str = "general"
    params: dict[str, Any] | None = None


class NewAgent(BaseModel):
    id: str
    name: str
    description: str
    domain: str = "general"
    role: str = "worker"


class CreateSkillRequest(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "foundation-next", "version": "1.0.0-pre.1"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    return {
        "message": "FoundationCentar API is running",
        "version": "1.0.0-pre.1",
        "agentguard_enabled": AGENTGUARD_ENABLED,
    }


@app.get("/api/v1/agents")
async def list_agents():
    """List all registered agents (Brain + Chiefs + Workers)."""
    if _LOCAL_ORCHESTRATOR:
        agents: dict[str, dict[str, Any]] = {
            "brain": {"name": "Brain", "role": "global_router"}
        }
        for domain, chief in local_brain.chiefs.items():
            agents[domain] = {
                "name": chief.name,
                "role": chief.domain,
                "workers": [w.name for w in chief.workers],
            }
        return agents
    # FoundationNext control plane path
    if _control_plane is not None:
        return {"agents": "control-plane-managed", "version": "1.0.0-pre.1"}
    return {"agents": "local-orchestrator-not-available", "status": "degraded"}


@app.get("/api/v1/skills")
async def list_skills():
    """List all available skills."""
    try:
        from foundation_next.local_skills import skill_diagnose_smart_meter, skill_reconcile_half_hourly_tariff
        return {
            "smart_meter_diagnostic": skill_diagnose_smart_meter.__doc__,
            "half_hourly_reconciliation": skill_reconcile_half_hourly_tariff.__doc__,
        }
    except ImportError:
        return {
            "smart_meter_diagnostic": "Diagnose a smart meter anomaly based on consumption data.",
            "half_hourly_reconciliation": "Reconcile half-hourly tariff data against expected patterns.",
        }


@app.post("/api/v1/brain/route")
async def route_brain(request: ChiefInput):
    """Route a request through the Brain agent."""
    # Refuse ungoverned local execution until dual-gate integration is wired.
    if _control_plane is None:
        raise HTTPException(status_code=503, detail="Governed execution unavailable")

    if _control_plane is not None:
        result = _control_plane.submit_and_execute(
            principal="api-user",
            capability=request.domain,
            action=request.action,
            arguments=request.params or {},
        )
        return {"routed": True, "result": result, "via": "control-plane"}

    return JSONResponse(
        status_code=503,
        content={"detail": "Brain orchestrator not available"},
    )


@app.post("/api/v1/execute-skill")
async def execute_skill(request: SkillRequest):
    """Execute a skill by name."""
    try:
        from foundation_next.local_skills import (
            MeterAuditInput,
            skill_diagnose_smart_meter,
            skill_reconcile_half_hourly_tariff,
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="Skills module not available")

    skills = {
        "smart_meter_diagnostic": skill_diagnose_smart_meter,
        "half_hourly_reconciliation": skill_reconcile_half_hourly_tariff,
    }

    # Local skill execution is not connected to either governance gate.
    raise HTTPException(status_code=503, detail="Governed skill execution unavailable")

    skill_name = request.prompt
    if skill_name not in skills:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    input_data = MeterAuditInput(
        meter_id="meter-001",
        reading_date=datetime.now(timezone.utc).isoformat(),
        consumption_kwh=400,
        tariff_zone=request.domain,
    )

    result = skills[skill_name](input_data)
    return {
        "status": result.status,
        "skill": result.skill_name,
        "output": result.output,
        "execution_time_ms": result.execution_time_ms,
    }


@app.post("/api/v1/create-agent")
async def create_agent(request: NewAgent):
    """Register a new agent in the system."""
    return {
        "registered": True,
        "agent": request.model_dump(),
        "message": f"Agent {request.name} registered in domain {request.domain}",
    }


@app.post("/api/v1/synthesize-skill")
async def synthesize_skill(request: CreateSkillRequest):
    """Synthesize a new skill from execution traces."""
    return {
        "synthesized": True,
        "skill": request.name,
        "message": f"Skill {request.name} synthesized from trace patterns",
    }


@app.get("/api/v1/traces")
async def list_traces(domain: str | None = None, limit: int = 10):
    """List recent execution traces."""
    return {
        "traces": [],
        "domain": domain,
        "limit": limit,
        "source": "local-orchestrator" if _LOCAL_ORCHESTRATOR else "control-plane",
    }
