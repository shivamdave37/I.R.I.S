"""Check launcher health handling and exact update rollback behavior."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    """Exercise startup rollback against a tiny isolated project folder."""

    def setUp(self):
        """Create temporary target, backup, and pending marker paths."""
        self.folder = tempfile.TemporaryDirectory()
        self.old_project = launcher.config.PROJECT_FOLDER
        self.old_data = launcher.config.DATA_FOLDER
        launcher.config.PROJECT_FOLDER = self.folder.name
        launcher.config.DATA_FOLDER = os.path.join(self.folder.name, "data")
        self.identifier = "abcdef012345"
        os.makedirs(os.path.join(self.folder.name, "iris"))
        target = os.path.join(self.folder.name, "iris", "iris.py")
        with open(target, "wb") as file_handle:
            file_handle.write(b"broken update")
        backup = os.path.join(self.folder.name, "data", "backups", self.identifier, "iris")
        os.makedirs(backup)
        with open(os.path.join(backup, "iris.py"), "wb") as file_handle:
            file_handle.write(b"original exact bytes\r\n")
        os.makedirs(launcher.config.DATA_FOLDER, exist_ok=True)
        with open(os.path.join(launcher.config.DATA_FOLDER, "pending_update.json"), "w", encoding="utf-8") as file_handle:
            json.dump({"id": self.identifier, "files": ["iris/iris.py"]}, file_handle)

    def tearDown(self):
        """Restore project settings and clean the temporary test project."""
        launcher.config.PROJECT_FOLDER = self.old_project
        launcher.config.DATA_FOLDER = self.old_data
        self.folder.cleanup()

    def test_failed_startup_restores_exact_backup_bytes(self):
        """The launcher rollback restores bytes and consumes its pending marker."""
        record = launcher._pending_record()
        self.assertEqual(record["id"], self.identifier)
        launcher._restore_pending(record)
        target = os.path.join(self.folder.name, "iris", "iris.py")
        with open(target, "rb") as file_handle:
            self.assertEqual(file_handle.read(), b"original exact bytes\r\n")
        self.assertFalse(os.path.exists(os.path.join(launcher.config.DATA_FOLDER, "pending_update.json")))

    def test_early_process_exit_uses_automatic_rollback_then_restarts(self):
        """A failed pending startup restores files and launches the restored app."""
        class FailedProcess:
            """Represent a child that exits before the health marker appears."""

            def poll(self):
                """Report that the candidate process already exited."""
                return 1

            def terminate(self):
                """Accept the launcher's stop request."""
                return None

            def wait(self, timeout=None):
                """Return a completed process status."""
                return 1

        class RestoredProcess:
            """Represent the restored program that starts normally."""

            def wait(self):
                """Return the normal exit status after the human closes Jarvis."""
                return 0

        launches = [FailedProcess(), RestoredProcess()]
        with patch.object(launcher, "_start_main", side_effect=launches):
            self.assertEqual(launcher.run(), 0)
        target = os.path.join(self.folder.name, "iris", "iris.py")
        with open(target, "rb") as file_handle:
            self.assertEqual(file_handle.read(), b"original exact bytes\r\n")


if __name__ == "__main__":
    unittest.main()
