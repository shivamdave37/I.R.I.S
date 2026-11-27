"""Unit tests for the isolated sandbox runner, trial skill cache, and fast retrieval index."""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import action_gateway
import dynamic_skills
import sandbox_runner
import task_planner


class SandboxRunnerTests(unittest.TestCase):
    """Test the isolated subprocess sandbox and AST security validator."""

    def test_valid_code_passes_ast_check(self):
        """Clean arithmetic or printing code is accepted."""
        code = "def run():\n    return 40 + 2\nprint(run())"
        is_valid, msg = sandbox_runner.validate_skill_source(code)
        self.assertTrue(is_valid)

    def test_eval_exec_and_compile_are_blocked(self):
        """Dynamic code execution calls are caught and rejected."""
        for banned in ("eval('1 + 1')", "exec('x = 2')", "__import__('os')"):
            is_valid, msg = sandbox_runner.validate_skill_source(f"def test():\n    {banned}")
            self.assertFalse(is_valid)
            self.assertIn("forbidden", msg.lower())

    def test_secret_access_references_are_blocked(self):
        """References to .env or API keys are rejected at syntax check time."""
        is_valid, msg = sandbox_runner.validate_skill_source("key = os.environ.get('GEMINI_API_KEY')")
        self.assertFalse(is_valid)
        self.assertIn("secrets", msg.lower())

    def test_socket_networking_is_blocked(self):
        """Network socket access is rejected."""
        is_valid, msg = sandbox_runner.validate_skill_source("import socket\ns = socket.socket()")
        self.assertFalse(is_valid)
        self.assertIn("forbidden", msg.lower())

    def test_safe_execution_captures_stdout(self):
        """Sandboxed subprocess runs clean code and captures output."""
        code = "print('TRIAL_SUCCESS_42')"
        result = sandbox_runner.execute_in_sandbox(code, timeout_seconds=3.0)
        self.assertTrue(result.success)
        self.assertEqual(result.output, "TRIAL_SUCCESS_42")
        self.assertEqual(result.exit_code, 0)

    def test_timeout_kills_infinite_loop(self):
        """A script that loops forever is terminated within the timeout limit."""
        code = "import time\nwhile True:\n    time.sleep(0.1)"
        result = sandbox_runner.execute_in_sandbox(code, timeout_seconds=0.5)
        self.assertFalse(result.success)
        self.assertTrue(result.timed_out)
        self.assertIn("timeout", result.error.lower())


class DynamicSkillsCacheTests(unittest.TestCase):
    """Test temporary skill registry, fast retrieval pathway, and lifecycle."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="iris_skills_test_")
        self.orig_dir = dynamic_skills.TEMP_SKILLS_DIR
        self.orig_file = dynamic_skills.REGISTRY_FILE
        dynamic_skills.TEMP_SKILLS_DIR = Path(self.temp_dir)
        dynamic_skills.REGISTRY_FILE = Path(self.temp_dir) / "registry.json"

    def tearDown(self):
        dynamic_skills.TEMP_SKILLS_DIR = self.orig_dir
        dynamic_skills.REGISTRY_FILE = self.orig_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_list_trial_skill(self):
        """Trial skills are saved to disk and indexed in the registry."""
        code = "print('Hello Chrome Profile')"
        success, skill_id = dynamic_skills.save_trial_skill(
            name="chrome_profile_launcher",
            description="Launches Chrome with Account 1",
            tags=["chrome", "profile", "browser"],
            source_code=code,
        )
        self.assertTrue(success)
        self.assertTrue(skill_id.startswith("trial_chrome_profile_launcher_"))

        all_skills = dynamic_skills.list_trial_skills()
        self.assertEqual(len(all_skills), 1)
        self.assertEqual(all_skills[0]["name"], "chrome_profile_launcher")
        self.assertEqual(all_skills[0]["status"], "trial")

    def test_fast_retrieval_pathway_by_tag_or_query(self):
        """Matching trial skills are retrieved in sub-milliseconds."""
        code = "print('Converting text')"
        dynamic_skills.save_trial_skill(
            name="csv_text_converter",
            description="Converts raw text to CSV rows",
            tags=["csv", "converter", "spreadsheet"],
            source_code=code,
        )

        # Query 1: by tag
        match1 = dynamic_skills.find_matching_trial_skill("spreadsheet")
        self.assertIsNotNone(match1)
        self.assertEqual(match1["name"], "csv_text_converter")

        # Query 2: by keyword in name
        match2 = dynamic_skills.find_matching_trial_skill("convert to csv")
        self.assertIsNotNone(match2)
        self.assertEqual(match2["name"], "csv_text_converter")

        # Query 3: completely unrelated query returns None
        match3 = dynamic_skills.find_matching_trial_skill("weather in tokyo")
        self.assertIsNone(match3)

    def test_execute_trial_skill_increments_run_count(self):
        """Executing a trial skill through the sandbox increments its verified run count."""
        code = "print('EXECUTED_DYNAMIC_SKILL')"
        success, skill_id = dynamic_skills.save_trial_skill(
            name="counter_test",
            description="Simple run counter test",
            tags=["test"],
            source_code=code,
        )
        self.assertTrue(success)

        res = dynamic_skills.execute_trial_skill(skill_id)
        self.assertTrue(res.success)
        self.assertEqual(res.output, "EXECUTED_DYNAMIC_SKILL")

        registry = dynamic_skills._load_registry()
        self.assertEqual(registry[skill_id]["run_count"], 1)

    def test_promotion_and_deletion_lifecycle(self):
        """Trial skills can be promoted to permanent status or cleanly removed."""
        code = "print('Lifecycle test')"
        _, skill_id = dynamic_skills.save_trial_skill("lifecycle", "test", ["temp"], code)

        # Promote
        promoted, msg = dynamic_skills.promote_trial_skill(skill_id)
        self.assertTrue(promoted)
        self.assertEqual(dynamic_skills._load_registry()[skill_id]["status"], "promoted")

        # Delete
        deleted, del_msg = dynamic_skills.delete_trial_skill(skill_id)
        self.assertTrue(deleted)
        self.assertEqual(len(dynamic_skills.list_trial_skills()), 0)


class GatewayIntegrationTests(unittest.TestCase):
    """Test Action Gateway approval gate for trial skills."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="iris_gw_test_")
        self.orig_dir = dynamic_skills.TEMP_SKILLS_DIR
        self.orig_file = dynamic_skills.REGISTRY_FILE
        dynamic_skills.TEMP_SKILLS_DIR = Path(self.temp_dir)
        dynamic_skills.REGISTRY_FILE = Path(self.temp_dir) / "registry.json"

    def tearDown(self):
        dynamic_skills.TEMP_SKILLS_DIR = self.orig_dir
        dynamic_skills.REGISTRY_FILE = self.orig_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_running_trial_skill_requires_typed_approval(self):
        """Trial skill execution is strictly gated by the Action Gateway."""
        code = "print('SECURE_OUTPUT')"
        _, skill_id = dynamic_skills.save_trial_skill("security_test", "test", ["gate"], code)

        # Case A: User approves with 'yes'
        output = action_gateway.execute("run_trial_skill", {"skill_id": skill_id}, lambda p: "yes")
        self.assertIn("SECURE_OUTPUT", output)

        # Case B: User denies
        with self.assertRaises(action_gateway.ApprovalDenied):
            action_gateway.execute("run_trial_skill", {"skill_id": skill_id}, lambda p: "no")


if __name__ == "__main__":
    unittest.main()
