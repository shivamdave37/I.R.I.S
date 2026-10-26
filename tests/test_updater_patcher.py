"""Check the patch pipeline's fixed safety scans and diff generation."""

import os
import unittest
from unittest.mock import patch

from updater import patcher


class PatcherTests(unittest.TestCase):
    """Exercise refusal rules without running candidate code."""

    def setUp(self):
        """Use a tiny existing allowed project file for repeatable proposals."""
        self.save_patch = patch.object(patcher.proposal_store, "save_proposal")
        self.save_patch.start()
        self.addCleanup(self.save_patch.stop)
        self.source = os.path.join(patcher.config.PROJECT_FOLDER, "main.py")
        with open(self.source, "r", encoding="utf-8") as file_handle:
            self.original = file_handle.read()

    def proposal(self, text, **kwargs):
        """Build a candidate while keeping sandbox execution mocked off."""
        kwargs.setdefault("run_tests", False)
        return patcher.build_proposal({"main.py": text}, "small safe edit", **kwargs)

    def test_diff_is_generated_from_full_text(self):
        """The displayed diff contains the actual file change from difflib."""
        proposal = self.proposal(self.original + "\n# harmless proposal\n")
        self.assertIn("# harmless proposal", proposal.diff)
        self.assertIn("main.py", proposal.diff)

    def test_refuses_non_tier_one_and_missing_targets(self):
        """Protected paths and new files never become patch proposals."""
        result = patcher.build_proposal({"confirm.py": "x = 1\n"}, "reason", run_tests=False)
        self.assertEqual(result.status, "REFUSED")
        with patch.object(patcher, "_read_original", side_effect=ValueError("missing")):
            result = self.proposal("x = 1\n")
        self.assertEqual(result.status, "REFUSED")

    def test_refuses_file_count_and_line_limits(self):
        """The file count and total changed-line caps are enforced."""
        many = {"main.py": self.original, "router.py": "x = 1\n", "ai.py": "x = 1\n", "voice.py": "x = 1\n"}
        self.assertEqual(patcher.build_proposal(many, "reason", run_tests=False).status, "REFUSED")
        result = self.proposal("\n".join("value = %d" % index for index in range(90)))
        self.assertEqual(result.status, "REFUSED")

    def test_refuses_syntax_error_and_protected_marker_change(self):
        """Invalid Python and altered protected lines are refused before tests."""
        result = self.proposal("def broken(:\n pass\n")
        self.assertEqual(result.status, "REFUSED")
        protected = "def keep():\n    answer = True\n    return answer  # PROTECTED\n"
        with patch.object(patcher, "_read_original", return_value=protected):
            result = self.proposal("def keep():\n    answer = False\n    return answer  # PROTECTED\n")
        self.assertEqual(result.status, "REFUSED")

    def test_refuses_each_banned_pattern(self):
        """Every explicitly banned token in added lines blocks the proposal."""
        examples = [
            "shell=True", "exec(", "eval(", "__import__", "importlib", "os.system",
            "socket", ".env", "API_KEY", "base64", "import subprocess\nsubprocess.run([])",
            "from urllib.request import urlopen\nurlopen('https://example.com')",
            "open('file.txt', 'w')",
        ]
        for snippet in examples:
            with self.subTest(snippet=snippet):
                with patch.object(patcher, "_read_original", return_value="value = 1\n"):
                    result = self.proposal("value = 1\n" + snippet + "\n")
                self.assertEqual(result.status, "REFUSED")

    def test_test_failure_does_not_become_ready(self):
        """A failed isolated test leaves the candidate unapprovable."""
        with patch.object(patcher, "_read_original", return_value="value = 1\n"), \
                patch.object(patcher.sandbox_test, "run_tests", return_value={"passed": False, "result": "failed"}):
            result = self.proposal("value = 2\n", run_tests=True)
        self.assertEqual(result.status, "TEST_FAILED")

    def test_planner_helper_can_change_while_ai_validator_stays_protected(self):
        """Planner behavior helpers remain patchable without changing the AI gate."""
        planner_path = os.path.join(patcher.config.PROJECT_FOLDER, "iris", "agent_planner.py")
        with open(planner_path, "r", encoding="utf-8") as file_handle:
            planner_text = file_handle.read()
        changed = planner_text.replace('"estimate_seconds": 2}', '"estimate_seconds": 1}', 1)
        proposal = patcher.build_proposal({"iris/agent_planner.py": changed}, "shorter estimate", run_tests=False)
        self.assertEqual(proposal.status, "READY")

    def test_permission_callback_cannot_be_patched_out(self):
        """Attempts to bypass the permission callback in iris.py are refused."""
        iris_path = os.path.join(patcher.config.PROJECT_FOLDER, "iris", "iris.py")
        with open(iris_path, "r", encoding="utf-8") as file_handle:
            iris_text = file_handle.read()
        tampered = iris_text.replace("return self._permission_callback(task)  # PROTECTED", "return True  # PROTECTED")
        proposal = patcher.build_proposal({"iris/iris.py": tampered}, "bypass permission", run_tests=False)
        self.assertEqual(proposal.status, "REFUSED")

    def test_resource_mapping_cannot_be_patched_out(self):
        """Attempts to remove sensitive resource mapping in agent_permissions.py are refused."""
        perm_path = os.path.join(patcher.config.PROJECT_FOLDER, "iris", "agent_permissions.py")
        with open(perm_path, "r", encoding="utf-8") as file_handle:
            perm_text = file_handle.read()
        tampered = perm_text.replace('return ["GIT_REPO"]  # PROTECTED', 'return []  # PROTECTED')
        proposal = patcher.build_proposal({"iris/agent_permissions.py": tampered}, "bypass git resource", run_tests=False)
        self.assertEqual(proposal.status, "REFUSED")


if __name__ == "__main__":
    unittest.main()
