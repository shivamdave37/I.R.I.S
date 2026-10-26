"""Check that updater tests run only in a bounded temporary project copy."""

import unittest
import os
import subprocess
import tempfile
from unittest.mock import patch

from updater import sandbox_test


class SandboxTests(unittest.TestCase):
    """Cover fixed timeout and candidate validation behavior."""

    def test_timeout_cannot_be_extended_or_shortened(self):
        """The update checker always uses its specified 120-second limit."""
        result = sandbox_test.run_tests({"main.py": "pass\n"}, timeout=999)
        self.assertFalse(result["passed"])

    def test_invalid_candidate_is_rejected(self):
        """A protected target is refused before project copy or execution."""
        with patch.object(sandbox_test.shutil, "copytree") as copy_project:
            result = sandbox_test.run_tests({"confirm.py": "pass\n"})
        self.assertFalse(result["passed"])
        copy_project.assert_not_called()

    def _temporary_project(self):
        """Create a minimal project whose paths exercise the real sandbox copier."""
        folder = tempfile.TemporaryDirectory()
        old_project = sandbox_test.config.PROJECT_FOLDER
        old_data = sandbox_test.config.DATA_FOLDER
        sandbox_test.config.PROJECT_FOLDER = folder.name
        sandbox_test.config.DATA_FOLDER = os.path.join(folder.name, "data")
        os.makedirs(os.path.join(folder.name, "tests"))
        with open(os.path.join(folder.name, "main.py"), "w", encoding="utf-8") as file_handle:
            file_handle.write("value = 1\n")
        with open(os.path.join(folder.name, ".env"), "w", encoding="utf-8") as file_handle:
            file_handle.write("GEMINI_API_KEY=do-not-copy\n")
        return folder, old_project, old_data

    def test_failing_test_in_copy_blocks_candidate_and_omits_env(self):
        """The copied suite failure blocks the update and the sandbox has no .env."""
        folder, old_project, old_data = self._temporary_project()
        try:
            with open(os.path.join(folder.name, "tests", "test_fail.py"), "w", encoding="utf-8") as file_handle:
                file_handle.write("import unittest\nclass FailingTest(unittest.TestCase):\n def test_fail(self):\n  self.fail('expected')\n")
            real_run = subprocess.run
            seen = []

            def inspect_then_run(command, cwd, **kwargs):
                """Check the copied tree before invoking only the fixed test command."""
                seen.append(not os.path.exists(os.path.join(cwd, ".env")))
                return real_run(command, cwd=cwd, **kwargs)

            with patch.object(sandbox_test.subprocess, "run", side_effect=inspect_then_run):
                result = sandbox_test.run_tests({"main.py": "value = 2\n"})
            self.assertFalse(result["passed"])
            self.assertEqual(seen, [True])
        finally:
            sandbox_test.config.PROJECT_FOLDER = old_project
            sandbox_test.config.DATA_FOLDER = old_data
            folder.cleanup()

    def test_timeout_is_enforced_on_fixed_command(self):
        """An exceeded 120-second test deadline fails the copied candidate."""
        folder, old_project, old_data = self._temporary_project()
        try:
            with patch.object(sandbox_test.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 120)) as run:
                result = sandbox_test.run_tests({"main.py": "value = 2\n"})
            self.assertFalse(result["passed"])
            self.assertEqual(run.call_args.kwargs["timeout"], 120)
        finally:
            sandbox_test.config.PROJECT_FOLDER = old_project
            sandbox_test.config.DATA_FOLDER = old_data
            folder.cleanup()


if __name__ == "__main__":
    unittest.main()
