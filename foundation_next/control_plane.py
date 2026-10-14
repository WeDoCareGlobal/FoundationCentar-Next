"""FoundationCentar application service.

Jobs persist before execution. The security gate runs before any agent handler.
Identity must come from a trusted authenticated upstream; this module does not
implement authentication.
"""
from typing import Any
from foundation_next.agents import AgentRegistry
from foundation_next.orchestrator import FoundationOrchestrator
from foundation_next.workflows import WorkflowEngine

class FoundationControlPlane:
    def __init__(self, workflows: WorkflowEngine, guard: FoundationOrchestrator, agents: AgentRegistry):
        self.workflows = workflows
        self.guard = guard
        self.agents = agents

    def submit_and_execute(self, *, principal: str, capability: str, action: str,
                           arguments: dict[str, Any]) -> dict[str, Any]:
        job_id = self.workflows.submit(principal=principal, capability=capability,
                                       action=action, arguments=arguments)
        def guarded_executor(**request):
            # The guard is the only authorized execution route. AgentRegistry is
            # for discovery/routing; actual execution must occur through the
            # guarded capability endpoint, not through a direct handler.
            self.agents.resolve(request["capability"])
            return self.guard.execute(**request)
        result = self.workflows.run(job_id, guarded_executor)
        return {"job_id": job_id, "result": result}
