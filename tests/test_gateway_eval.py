import unittest
from foundation_next.mcp_gateway import MCPGateway, ToolError, ToolSpec
from foundation_next.evaluation import EvaluationEvent, Evaluator


class GatewayEvaluationTests(unittest.TestCase):
    def test_gateway_allowlisted_execution(self):
        gateway = MCPGateway()
        gateway.register(ToolSpec("search", "rag"), lambda args: {"status": "success", "query": args["query"]})
        result = gateway.execute(tool="search", capability="rag", arguments={"query": "test"}, authorization="decision-1")
        self.assertEqual(result["query"], "test")

    def test_gateway_rejects_unknown_tool(self):
        gateway = MCPGateway()
        with self.assertRaises(ToolError):
            gateway.execute(tool="shell", capability="ops", arguments={}, authorization="decision-1")

    def test_gateway_rejects_missing_authorization(self):
        gateway = MCPGateway()
        gateway.register(ToolSpec("search", "rag"), lambda _: {"status": "success"})
        with self.assertRaises(ToolError):
            gateway.execute(tool="search", capability="rag", arguments={}, authorization="")

    def test_gateway_rejects_unconfirmed_result(self):
        gateway = MCPGateway()
        gateway.register(ToolSpec("search", "rag"), lambda _: {"status": "pending"})
        with self.assertRaises(ToolError):
            gateway.execute(tool="search", capability="rag", arguments={}, authorization="decision-1")

    def test_evaluation_summary(self):
        evaluator = Evaluator()
        evaluator.record(EvaluationEvent("j1", "rag", "completed", 10))
        evaluator.record(EvaluationEvent("j2", "rag", "failed", 30))
        self.assertEqual(evaluator.summary()["success_rate"], 0.5)
        self.assertEqual(evaluator.summary()["mean_latency_ms"], 20)

    def test_evaluation_empty_is_unknown(self):
        self.assertIsNone(Evaluator().summary()["success_rate"])
