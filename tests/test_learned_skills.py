"""Check Stage 6C learned-skill safety, approvals, routing, and local Git limits."""

import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import config
from iris import agent_permissions, agent_planner
from iris.permissions import SENSITIVE_RESOURCES
from skills import learned_skills
from skills import github_tools


GOOD_CODE = '''SKILL_NAME = "Coin Flip"
KEYWORDS = ["coin", "flip"]
RESOURCES = []
def run(command):
    """Return one fixed coin-flip message."""
    return "heads"
'''


class LearnedSkillCheckerTests(unittest.TestCase):
    """Cover the approved subset of Python accepted for learned skills."""

    def test_accepts_small_valid_skill(self):
        """Accept the required names, literal metadata, and text result function."""
        accepted, message, metadata = learned_skills.check_code(GOOD_CODE)
        self.assertTrue(accepted, message)
        self.assertEqual(metadata["resources"], [])

    def test_rejects_each_disallowed_import(self):
        """Reject imports outside the fixed standard-library and psutil list."""
        for module in ("os", "sys", "subprocess", "socket", "requests", "shutil", "pathlib", "ctypes", "importlib", "threading"):
            source = GOOD_CODE.replace('SKILL_NAME =', f'import {module}\nSKILL_NAME =')
            with self.subTest(module=module):
                self.assertFalse(learned_skills.check_code(source)[0])

    def test_rejects_import_aliases_star_and_unsafe_from_names(self):
        """Reject import tricks that hide module or member names."""
        for statement in ("import math as m", "from math import *", "from math import sqrt as s"):
            source = GOOD_CODE.replace('SKILL_NAME =', statement + "\nSKILL_NAME =")
            with self.subTest(statement=statement):
                self.assertFalse(learned_skills.check_code(source)[0])

    def test_rejects_every_blocked_builtin_name(self):
        """Reject dynamic execution, input/output, and reflective builtins."""
        names = sorted(learned_skills._BLOCKED_NAMES)
        for name in names:
            source = GOOD_CODE.replace('return "heads"', f"return {name}('x')")
            with self.subTest(name=name):
                self.assertFalse(learned_skills.check_code(source)[0])

    def test_rejects_private_attributes_and_dunder_access(self):
        """Block attribute-based escapes such as __class__ and random internals."""
        for expression in ("command.__class__", "__builtins__.__dict__", "random._os"):
            source = GOOD_CODE.replace('return "heads"', f"return str({expression})")
            with self.subTest(expression=expression):
                self.assertFalse(learned_skills.check_code(source)[0])
        private_import = GOOD_CODE.replace('SKILL_NAME =', 'from random import _os\nSKILL_NAME =')
        self.assertFalse(learned_skills.check_code(private_import)[0])

    def test_rejects_nested_functions_lambdas_decorators_and_classes(self):
        """Keep candidate code flat and without decorators or class behavior."""
        variants = (
            GOOD_CODE.replace("def run(command):", "@staticmethod\ndef run(command):"),
            GOOD_CODE.replace('    return "heads"', '    helper = lambda: "heads"\n    return helper()'),
            GOOD_CODE.replace('    return "heads"', '    def helper():\n        return "heads"\n    return helper()'),
            GOOD_CODE.replace('def run(command):', 'class Helper:\n    pass\ndef run(command):'),
        )
        for source in variants:
            with self.subTest(source=source):
                self.assertFalse(learned_skills.check_code(source)[0])

    def test_rejects_while_true_without_break(self):
        """Reject a constant infinite loop before any candidate process starts."""
        source = GOOD_CODE.replace('    return "heads"', '    while True:\n        pass\n    return "heads"')
        self.assertFalse(learned_skills.check_code(source)[0])
        nested_break = GOOD_CODE.replace('    return "heads"', '    while True:\n        while True:\n            break\n    return "heads"')
        self.assertFalse(learned_skills.check_code(nested_break)[0])

    def test_rejects_wrong_signature_metadata_unknown_resource_and_long_file(self):
        """Require exact fields, known resource names, and the 120-line cap."""
        variants = (
            GOOD_CODE.replace("def run(command):", "def run(command, other):"),
            GOOD_CODE.replace("def run(command):", "def run(command: int):"),
            GOOD_CODE.replace("def run(command):", "def run(command, /):"),
            GOOD_CODE.replace('RESOURCES = []', 'RESOURCES = ["UNKNOWN"]'),
            GOOD_CODE.replace('KEYWORDS = ["coin", "flip"]', 'KEYWORDS = ["Coin"]'),
            GOOD_CODE.replace('SKILL_NAME = "Coin Flip"', 'SKILL_NAME = "Coin Flip"\nOTHER = 3'),
            GOOD_CODE + "\n" * 121,
        )
        for source in variants:
            with self.subTest(source=source[:60]):
                self.assertFalse(learned_skills.check_code(source)[0])


class LearnedSkillFlowTests(unittest.TestCase):
    """Verify approval ordering, data paths, Iris resources, and undo behavior."""

    def setUp(self):
        """Use a disposable project tree for generated proposal and registry data."""
        self.temporary = tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER)
        self.root = self.temporary.name
        self.data = os.path.join(self.root, "data")
        self.folder_patch = patch.object(config, "PROJECT_FOLDER", self.root)
        self.data_patch = patch.object(config, "DATA_FOLDER", self.data)
        self.folder_patch.start()
        self.data_patch.start()
        self.addCleanup(self.folder_patch.stop)
        self.addCleanup(self.data_patch.stop)
        self.addCleanup(self.temporary.cleanup)
        self.startup_patch = patch.object(learned_skills, "_STARTUP_HASHES", None)
        self.startup_patch.start()
        self.addCleanup(self.startup_patch.stop)
        learned_skills._LOCK.acquire()
        learned_skills._LOCK.release()

    def test_first_no_or_spoken_answer_does_not_write_candidate(self):
        """Require an exact keyboard yes before creating or running the proposal."""
        with patch.object(learned_skills.input_broker, "enabled", True):
            with patch.object(learned_skills, "_request_code", return_value=GOOD_CODE):
                with patch.object(learned_skills, "_protected_hashes", return_value={}):
                    with patch.object(learned_skills, "request_input", return_value="yes please"):
                        with patch("sys.stdout"):
                            reply = learned_skills.add_skill("flip a coin")
        self.assertIn("No skill was installed", reply)
        self.assertFalse(os.path.exists(os.path.join(self.root, "proposed_skills", "coin_flip.py")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "skills", "learned", "coin_flip.py")))

    def test_two_typed_approvals_are_ordered_around_isolated_test(self):
        """Run the isolated check only after approval one and install after approval two."""
        sequence = []
        def test_candidate(path):
            """Record the subprocess test position in the approval sequence."""
            sequence.append("test")
            self.assertTrue(os.path.isfile(path))
            return True, "heads"
        with patch.object(learned_skills.input_broker, "enabled", True):
            with patch.object(learned_skills, "_request_code", return_value=GOOD_CODE):
                with patch.object(learned_skills, "_protected_hashes", return_value={}):
                    with patch.object(learned_skills, "request_input", side_effect=lambda prompt, timeout=60: sequence.append("yes") or "yes"):
                        with patch.object(learned_skills, "_subprocess_test", side_effect=test_candidate):
                            with patch.object(learned_skills, "_install", side_effect=lambda code, metadata, path: sequence.append("install") or "installed"):
                                with patch("sys.stdout"):
                                    reply = learned_skills.add_skill("flip a coin")
        self.assertEqual(reply, "installed")
        self.assertEqual(sequence, ["yes", "test", "yes", "install"])

    def test_failed_candidate_never_installs_and_proposal_is_removed(self):
        """Delete a candidate after its bounded isolated test fails."""
        with patch.object(learned_skills.input_broker, "enabled", True):
            with patch.object(learned_skills, "_request_code", return_value=GOOD_CODE):
                with patch.object(learned_skills, "_protected_hashes", return_value={}):
                    with patch.object(learned_skills, "request_input", return_value="yes"):
                        with patch.object(learned_skills, "_subprocess_test", return_value=(False, "failed")):
                            with patch.object(learned_skills, "_install") as install:
                                with patch("sys.stdout"):
                                    reply = learned_skills.add_skill("flip a coin")
        install.assert_not_called()
        self.assertIn("No skill was installed", reply)
        self.assertFalse(os.path.exists(os.path.join(self.root, "proposed_skills", "coin_flip.py")))

    def test_second_no_leaves_no_installed_skill(self):
        """Require the second typed yes after the passing isolated test."""
        with patch.object(learned_skills.input_broker, "enabled", True):
            with patch.object(learned_skills, "_request_code", return_value=GOOD_CODE):
                with patch.object(learned_skills, "_protected_hashes", return_value={}):
                    with patch.object(learned_skills, "request_input", side_effect=["yes", "no"]):
                        with patch.object(learned_skills, "_subprocess_test", return_value=(True, "heads")):
                            with patch.object(learned_skills, "_install") as install:
                                with patch("sys.stdout"):
                                    reply = learned_skills.add_skill("flip a coin")
        install.assert_not_called()
        self.assertIn("No skill was installed", reply)
        self.assertFalse(os.path.exists(os.path.join(self.root, "skills", "learned", "coin_flip.py")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "proposed_skills", "coin_flip.py")))

    def test_protected_file_change_after_approval_aborts(self):
        """Stop when a protected file hash differs after the typed response."""
        with patch.object(learned_skills.input_broker, "enabled", True):
            with patch.object(learned_skills, "_protected_hashes", return_value={"SPEC.md": "new"}):
                with patch.object(learned_skills, "request_input", return_value="yes"):
                    self.assertFalse(learned_skills._approval("approve", {"SPEC.md": "old"}))

    def test_proposal_path_traversal_is_refused(self):
        """Refuse any resolved path outside the dedicated proposal folder."""
        allowed = os.path.join(self.root, "proposed_skills")
        self.assertFalse(learned_skills._safe_path(os.path.join(allowed, "..", "outside.py"), [allowed]))

    def test_unknown_skill_resource_is_rejected_by_checker(self):
        """Reject a resource name that is not declared by Iris."""
        candidate = GOOD_CODE.replace("RESOURCES = []", 'RESOURCES = ["NOT_A_RESOURCE"]')
        self.assertFalse(learned_skills.check_code(candidate)[0])

    def test_runner_times_out_and_checks_for_string_result(self):
        """Stop slow candidate processes and reject malformed subprocess results."""
        candidate = os.path.join(self.root, "proposed_skills", "candidate.py")
        os.makedirs(os.path.dirname(candidate))
        with open(candidate, "w", encoding="utf-8") as candidate_file:
            candidate_file.write(GOOD_CODE)
        with patch("skills.learned_skills.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("python", 5)):
            self.assertIn("5 seconds", learned_skills._subprocess_test(candidate)[1])
        with patch("skills.learned_skills.subprocess.run", return_value=Mock(returncode=0, stdout='{"result": 4}\n')):
            self.assertFalse(learned_skills._subprocess_test(candidate)[0])

    def test_real_slow_candidate_process_is_killed_by_timeout(self):
        """Exercise subprocess termination with a safe, deliberately slow fixture."""
        candidate = os.path.join(self.root, "proposed_skills", "slow_skill.py")
        os.makedirs(os.path.dirname(candidate))
        slow_code = GOOD_CODE.replace('    return "heads"', '    time.sleep(1)\n    return "heads"').replace('SKILL_NAME = "Coin Flip"', 'import time\nSKILL_NAME = "Slow Skill"')
        with open(candidate, "w", encoding="utf-8") as candidate_file:
            candidate_file.write(slow_code)
        with patch.object(learned_skills, "_ISOLATED_TIMEOUT_SECONDS", 0.05):
            passed, message = learned_skills._subprocess_test(candidate)
        self.assertFalse(passed)
        self.assertIn("5 seconds", message)

    def test_registry_keyword_runs_via_declared_iris_resources(self):
        """Plan a learned keyword as a task holding only its declared resources."""
        os.makedirs(os.path.join(self.root, "data"))
        os.makedirs(os.path.join(self.root, "skills", "learned"))
        with open(os.path.join(self.root, "data", "learned_skills.json"), "w", encoding="utf-8") as registry_file:
            json.dump({"coin_flip": {"name": "Coin Flip", "file": "coin_flip.py", "keywords": ["coin", "flip"], "resources": ["API_QUOTA"]}}, registry_file)
        planned = agent_planner.plan("flip the coin")
        needed, allowed = agent_permissions.inspect("flip the coin")
        self.assertEqual(planned["steps"], ["learned_skills"])
        self.assertIn("API_QUOTA", needed)
        self.assertTrue(allowed)

    def test_learned_resource_is_sensitive(self):
        """Require a typed approval every time a skill is installed or undone."""
        self.assertIn("LEARNED_SKILLS", SENSITIVE_RESOURCES)

    def test_undo_removes_registry_and_skill_then_commits(self):
        """Remove a registered learned skill and use only the local fixed helper."""
        learned_folder = os.path.join(self.root, "skills", "learned")
        os.makedirs(learned_folder)
        os.makedirs(self.data)
        skill_path = os.path.join(learned_folder, "coin_flip.py")
        with open(skill_path, "w", encoding="utf-8") as skill_file:
            skill_file.write(GOOD_CODE)
        with open(os.path.join(self.data, "learned_skills.json"), "w", encoding="utf-8") as registry_file:
            json.dump({"coin_flip": {"name": "Coin Flip", "file": "coin_flip.py", "keywords": ["coin"], "resources": []}}, registry_file)
        with patch("skills.github_tools.commit_learned_skill", return_value=(True, "local")) as commit:
            self.assertIn("Removed and locally committed", learned_skills.undo_last_skill())
        commit.assert_called_once_with("coin_flip", deleted=True)
        self.assertFalse(os.path.exists(skill_path))
        self.assertEqual(learned_skills._registry(), {})

    def test_fixed_git_helper_commits_exact_paths_without_push(self):
        """Stage only the skill and registry after confirming the index is clean."""
        def fake_git(arguments):
            """Return controlled Git statuses without starting Git."""
            if arguments[:3] == ["diff", "--cached", "--name-only"]:
                if len(git_calls) == 0:
                    git_calls.append(arguments)
                    return Mock(returncode=0, stdout="")
                return Mock(returncode=0, stdout="data/learned_skills.json\nskills/learned/coin_flip.py\n")
            git_calls.append(arguments)
            return Mock(returncode=0, stdout="")
        git_calls = []
        with patch("skills.github_tools._run_git", side_effect=fake_git):
            success, message = github_tools.commit_learned_skill("coin_flip")
        self.assertTrue(success, message)
        self.assertIn(["add", "-f", "--", "skills/learned/coin_flip.py", "data/learned_skills.json"], git_calls)
        self.assertIn(["commit", "-m", "Learned skill: coin_flip"], git_calls)
        self.assertFalse(any(command[0] == "push" for command in git_calls))


if __name__ == "__main__":
    unittest.main()
