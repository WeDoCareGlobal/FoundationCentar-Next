import unittest
from foundation_next.agents import AgentRegistry, AgentSpec, RoutingError

class AgentTests(unittest.TestCase):
    def test_routes_by_capability(self):
        r = AgentRegistry()
        r.register(AgentSpec("b", frozenset({"rag"})), lambda *_: {"status": "success"})
        r.register(AgentSpec("a", frozenset({"rag"})), lambda *_: {"status": "success"})
        self.assertEqual(r.resolve("rag").agent_id, "a")

    def test_disabled_is_not_routed(self):
        r = AgentRegistry()
        r.register(AgentSpec("a", frozenset({"rag"}), enabled=False), lambda *_: {})
        with self.assertRaises(RoutingError):
            r.resolve("rag")

    def test_no_fabricated_success(self):
        r = AgentRegistry()
        r.register(AgentSpec("a", frozenset({"rag"})), lambda *_: {"status": "pending"})
        with self.assertRaises(RoutingError):
            r.execute("rag", "query", {})
