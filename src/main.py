from __future__ import annotations

from typing import Any

from fastapi import FastAPI

app = FastAPI(title="FoundationCentar", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/v1/agents")
async def agents() -> dict[str, Any]:
    return {
        "brain": "global_router",
        "chiefs": [
            "operations",
            "devops",
            "research",
            "finance_legal",
            "marketing_sales",
        ],
        "workers": "default_pool",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
