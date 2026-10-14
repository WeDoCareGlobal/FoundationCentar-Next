import unittest
from unittest.mock import patch

from foundation_next.token_auth import SignedIngress


class SignedIngressTests(unittest.TestCase):
    def setUp(self):
        self.auth = SignedIngress(b"test-secret-material-with-32-bytes-minimum", "internal", "foundation")

    def test_valid_signed_identity(self):
        token = self.auth.issue(subject="alice", tenant_id="a")
        identity = self.auth.verify(token)
        self.assertEqual((identity.subject, identity.tenant_id), ("alice", "a"))

    def test_tampered_token_rejected(self):
        token = self.auth.issue(subject="alice", tenant_id="a")
        with self.assertRaises(PermissionError):
            self.auth.verify(token[:-1] + ("A" if token[-1] != "A" else "B"))

    def test_wrong_audience_rejected(self):
        other = SignedIngress(self.auth.secret, "internal", "other")
        with self.assertRaises(PermissionError):
            other.verify(self.auth.issue(subject="alice", tenant_id="a"))

    def test_expired_token_rejected(self):
        with patch("foundation_next.token_auth.time.time", return_value=1000):
            token = self.auth.issue(subject="alice", tenant_id="a", ttl_seconds=1)
        with patch("foundation_next.token_auth.time.time", return_value=1002):
            with self.assertRaises(PermissionError):
                self.auth.verify(token)
