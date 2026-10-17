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

    def test_api_is_not_accidentally_exposed(self):
        response = self.client.post("/api/actions", json={"action": "execute"})
        self.assertEqual(response.status_code, 503)

    def test_metrics_unconfigured(self):
        self.assertEqual(self.client.get("/metrics").status_code, 503)
