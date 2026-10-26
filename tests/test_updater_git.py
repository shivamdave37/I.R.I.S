"""Check that the update Git helper stages only approved files and never pushes."""

import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from skills import github_tools


class UpdateGitTests(unittest.TestCase):
    """Mock fixed Git calls and verify the updater cannot push."""

    def test_commit_stages_exact_targets_and_uses_local_commit(self):
        """The helper commits an exact TIER 1 list and issues no push command."""
        responses = [
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout="main.py\n"),
            SimpleNamespace(returncode=0, stdout=""),
        ]
        with patch.object(github_tools, "_run_git", side_effect=responses) as run_git:
            success, _ = github_tools.commit_update(["main.py"], "abcdef012345", "reason")
        self.assertTrue(success)
        self.assertEqual(run_git.call_args_list[-1], call(["commit", "-m", "Iris update abcdef012345: reason"]))
        self.assertFalse(any("push" in arguments for (arguments,), _ in run_git.call_args_list))

    def test_nonempty_index_blocks_commit(self):
        """Existing staged work prevents the updater from committing anything."""
        with patch.object(github_tools, "_run_git", return_value=SimpleNamespace(returncode=0, stdout="other.py\n")) as run_git:
            success, _ = github_tools.commit_update(["main.py"], "abcdef012345", "reason")
        self.assertFalse(success)
        run_git.assert_called_once_with(["diff", "--cached", "--name-only"])

    def test_commit_failure_resets_only_approved_staged_path(self):
        """A failed local commit resets the updater's staged target and stops."""
        responses = [
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout="main.py\n"),
            SimpleNamespace(returncode=1, stdout=""),
            SimpleNamespace(returncode=0, stdout=""),
        ]
        with patch.object(github_tools, "_run_git", side_effect=responses) as run_git:
            success, _ = github_tools.commit_update(["main.py"], "abcdef012345", "reason")
        self.assertFalse(success)
        self.assertEqual(run_git.call_args_list[-1], call(["reset", "--", "main.py"]))


if __name__ == "__main__":
    unittest.main()
