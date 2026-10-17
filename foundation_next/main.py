"""Minimal ASGI entrypoint for container readiness.

Business endpoints are intentionally unavailable until authenticated routes are
wired through the existing control-plane security boundary.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="FoundationCentar Next")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "foundation-next"}


@app.get("/metrics")
def metrics() -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Telemetry not configured"})


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def unavailable(path: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Authenticated API not configured"})
