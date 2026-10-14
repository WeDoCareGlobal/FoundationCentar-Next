import unittest

from foundation_next.policy_engine import Policy, evaluate
from foundation_next.secured_control_plane import PolicyDenied, SecuredControlPlane


class PolicyTests(unittest.TestCase):
    def test_default_deny(self):
        self.assertFalse(evaluate(Policy(frozenset()), capability="rag").allowed)

    def test_explicit_deny_overrides_allow(self):
        policy = Policy(frozenset({"rag"}), denied_capabilities=frozenset({"rag"}))
        self.assertEqual(evaluate(policy, capability="rag").reason, "explicit_deny")

    def test_allowed_capability(self):
        self.assertTrue(evaluate(Policy(frozenset({"rag"})), capability="rag").allowed)

    def test_approval_required(self):
        policy = Policy(frozenset({"deploy"}), require_approval=frozenset({"deploy"}))
        self.assertEqual(evaluate(policy, capability="deploy").reason, "approval_required")

    def test_approval_reference_not_sufficient_to_execute(self):
        class FakeApplication:
            def submit_and_execute(self, **kwargs):
                raise AssertionError("must not dispatch")
        app = SecuredControlPlane(
            FakeApplication(),
            Policy(frozenset({"deploy"}), require_approval=frozenset({"deploy"})),
        )
        with self.assertRaises(PolicyDenied):
            app.execute(principal="alice", capability="deploy", action="start",
                        arguments={}, approval_id="unverified-id")

    def test_policy_denial_does_not_dispatch(self):
        class FakeApplication:
            def submit_and_execute(self, **kwargs):
                raise AssertionError("must not dispatch")
        app = SecuredControlPlane(FakeApplication(), Policy(frozenset()))
        with self.assertRaises(PolicyDenied):
            app.execute(principal="alice", capability="rag", action="query", arguments={})
