"""Privacy-minimal evaluation metrics for workflow executions."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationEvent:
    job_id: str
    capability: str
    outcome: str
    latency_ms: float

    def __post_init__(self) -> None:
        if not self.job_id or not self.capability:
            raise ValueError("Missing evaluation identity")
        if self.outcome not in ("completed", "failed", "denied"):
            raise ValueError("Invalid evaluation outcome")
        if self.latency_ms < 0:
            raise ValueError("Latency cannot be negative")


class Evaluator:
    def __init__(self) -> None:
        self.events: list[EvaluationEvent] = []

    def record(self, event: EvaluationEvent) -> None:
        self.events.append(event)

    def summary(self) -> dict[str, Any]:
        count = len(self.events)
        successful = sum(event.outcome == "completed" for event in self.events)
        return {
            "count": count,
            "success_count": successful,
            "success_rate": successful / count if count else None,
            "mean_latency_ms": (
                sum(event.latency_ms for event in self.events) / count if count else None
            ),
        }
