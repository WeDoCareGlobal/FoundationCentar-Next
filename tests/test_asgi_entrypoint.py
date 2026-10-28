"""ASGI entrypoint smoke tests and fail-closed execution boundary checks."""
import unittest

from fastapi.testclient import TestClient

from foundation_next.main import app


class ASGIEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_unknown_endpoint_not_exposed(self):
        response = self.client.post("/api/actions", json={"action": "execute"})
        self.assertEqual(response.status_code, 404)

    def test_metrics_endpoint_available(self):
        self.assertEqual(self.client.get("/metrics").status_code, 200)

    def test_brain_route_requires_governed_authenticated_execution(self):
        response = self.client.post(
            "/api/v1/brain/route",
            json={"action": "execute", "domain": "rag"},
        )
        self.assertEqual(response.status_code, 503)

    def test_skill_execution_fails_closed(self):
        response = self.client.post(
            "/api/v1/execute-skill",
            json={"prompt": "smart_meter_diagnostic"},
        )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
