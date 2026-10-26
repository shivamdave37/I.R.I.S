"""Check typed proposal decisions, backup application, and exact rollback."""

import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from iris.tasks import Task, TaskState
from updater import apply as updater_apply
from updater.proposal import Proposal


class ApplyTests(unittest.TestCase):
    """Use temporary project files to test the approval and backup workflow."""

    def setUp(self):
        """Create one small project tree and restore global paths after each case."""
        self.folder = tempfile.TemporaryDirectory()
        self.old_project = updater_apply.config.PROJECT_FOLDER
        self.old_data = updater_apply.config.DATA_FOLDER
        updater_apply.config.PROJECT_FOLDER = self.folder.name
        updater_apply.config.DATA_FOLDER = os.path.join(self.folder.name, "data")
        os.makedirs(updater_apply.config.DATA_FOLDER)
        self.target = os.path.join(self.folder.name, "main.py")
        with open(self.target, "wb") as source:
            source.write(b"print('original')\r\n")
        self.original_hash = hashlib.sha256(b"print('original')\r\n").hexdigest()
        self.proposal = Proposal(
            id="0123456789ab", reason="small safe update", requested_by="admin",
            files={"main.py": "print('updated')\n"}, diff="-old\n+new\n", status="READY",
            hash="", base_hashes={"main.py": self.original_hash},
            risk_summary={"files": []}, test_result={"passed": True, "result": "passed"},
        )
        from updater.patcher import _candidate_hash
        self.proposal.hash = _candidate_hash(self.proposal.reason, self.proposal.requested_by,
                                             self.proposal.files, self.proposal.base_hashes, 0)

    def tearDown(self):
        """Restore global project paths and remove only this test's temporary tree."""
        updater_apply.config.PROJECT_FOLDER = self.old_project
        updater_apply.config.DATA_FOLDER = self.old_data
        self.folder.cleanup()

    def test_approval_is_bound_to_hash_and_deny_changes_nothing(self):
        """A typed approval returns the exact hash while deny stores no edits."""
        with patch.object(updater_apply.proposal_store, "find_proposal", return_value=self.proposal), \
                patch.object(updater_apply, "_base_files_match", return_value=True):
            approved, message = updater_apply.review_proposal(self.proposal.id, ask=lambda question, choices: "1")
            self.assertEqual(approved, {"id": self.proposal.id, "hash": self.proposal.hash})
            self.assertEqual(message, "Approved.")
            denied, _ = updater_apply.review_proposal(self.proposal.id, ask=lambda question, choices: "3")
        self.assertIsNone(denied)
        self.assertEqual(self.proposal.status, "DENIED")
        with open(self.target, "rb") as original:
            self.assertEqual(original.read(), b"print('original')\r\n")

    def test_apply_writes_backup_and_rollback_restores_exact_bytes(self):
        """Applying writes a local backup, then rollback restores original bytes."""
        with patch.object(updater_apply.proposal_store, "find_proposal", return_value=self.proposal), \
                patch.object(updater_apply.proposal_store, "save_proposal"), \
                patch("skills.github_tools.commit_update", return_value=(True, "committed locally")):
            applied, _ = updater_apply.apply_approved({"id": self.proposal.id, "hash": self.proposal.hash})
            self.assertTrue(applied)
            with open(self.target, "rb") as updated:
                self.assertEqual(updated.read(), b"print('updated')\n")
            backup = os.path.join(self.folder.name, "data", "backups", self.proposal.id, "main.py")
            with open(backup, "rb") as saved:
                self.assertEqual(saved.read(), b"print('original')\r\n")
            self.proposal.status = "APPLIED_PENDING_RESTART"
            with patch.object(updater_apply.proposal_store, "load_proposals", return_value=[self.proposal]):
                result = updater_apply.rollback_last(ask=lambda question, choices: "yes")
        self.assertIn("restored", result.lower())
        with open(self.target, "rb") as restored:
            self.assertEqual(restored.read(), b"print('original')\r\n")

    def test_apply_rejects_running_tasks_and_changed_hash(self):
        """A running task or altered approval token prevents file writes."""
        task = Task(1, "running", "command", state=TaskState.RUNNING)
        fake_supervisor = type("Supervisor", (), {"tasks": {1: task}})()
        with patch.object(updater_apply.proposal_store, "find_proposal", return_value=self.proposal):
            applied, _ = updater_apply.apply_approved({"id": self.proposal.id, "hash": self.proposal.hash}, fake_supervisor)
            changed, _ = updater_apply.apply_approved({"id": self.proposal.id, "hash": "wrong"})
        self.assertFalse(applied)
        self.assertFalse(changed)
        with open(self.target, "rb") as original:
            self.assertEqual(original.read(), b"print('original')\r\n")

    def test_other_way_writes_only_a_request_file(self):
        """The human handoff option writes a note and leaves source unchanged."""
        with patch.object(updater_apply.proposal_store, "find_proposal", return_value=self.proposal), \
                patch.object(updater_apply, "_base_files_match", return_value=True):
            answers = iter(("4", "please explain this update"))
            approval, result = updater_apply.review_proposal(
                self.proposal.id, ask=lambda question, choices: next(answers))
        self.assertIsNone(approval)
        self.assertIn("Wrote the human request", result)
        request = os.path.join(self.folder.name, "data", "update_requests", self.proposal.id + ".md")
        self.assertTrue(os.path.isfile(request))
        with open(self.target, "rb") as original:
            self.assertEqual(original.read(), b"print('original')\r\n")


if __name__ == "__main__":
    unittest.main()
