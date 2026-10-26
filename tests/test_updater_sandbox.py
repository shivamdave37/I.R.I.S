"""Check that updater tests run only in a bounded temporary project copy."""

import unittest
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


if __name__ == "__main__":
    unittest.main()
