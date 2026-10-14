import os
import tempfile
import unittest

from foundation_next.audit_journal import AuditJournal


class AuditJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "audit.db")
        self.journal = AuditJournal(self.path)

    def test_persists_and_verifies_after_reopen(self):
        self.assertEqual(self.journal.append(actor="alice", action="query", resource="rag"), 1)
        self.assertEqual(self.journal.append(actor="bob", action="review", resource="job"), 2)
        self.assertTrue(AuditJournal(self.path).verify())

    def test_tampered_row_fails_integrity(self):
        self.journal.append(actor="alice", action="query", resource="rag")
        with self.journal._connect() as db:
            db.execute("UPDATE audit_events SET action='changed' WHERE seq=1")
        self.assertFalse(self.journal.verify())

    def test_removed_middle_row_detected(self):
        for name in ("one", "two", "three"):
            self.journal.append(actor="alice", action=name, resource="job")
        with self.journal._connect() as db:
            db.execute("DELETE FROM audit_events WHERE seq=2")
        self.assertFalse(self.journal.verify())

    def test_empty_fields_rejected(self):
        with self.assertRaises(ValueError):
            self.journal.append(actor="", action="query", resource="rag")
