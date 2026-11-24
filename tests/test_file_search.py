"""Test bounded file-name search and exact approved opening with temporary roots."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import action_gateway
import config
import router
import skills
import task_planner
from task_planner import PlanStep


class FileSearchTests(unittest.TestCase):
    """Keep file lookup inside an approved root and away from file contents."""

    def setUp(self):
        """Create one disposable approved folder for each test."""
        self.temporary = tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER)
        self.root = Path(self.temporary.name)
        self.root_config = patch.object(config, "FILE_SEARCH_ROOTS", [self.root])
        self.root_config.start()

    def tearDown(self):
        """Restore configuration and remove only this test's temporary folder."""
        self.root_config.stop()
        self.temporary.cleanup()
        skills._FILE_SEARCH_RESULTS = []

    def test_search_finds_files_and_folders_without_reading_contents(self):
        """Name matching identifies both kinds and never includes file body text."""
        document = self.root / "report-2026.txt"
        document.write_text("PRIVATE_BODY_MARKER", encoding="utf-8")
        (self.root / "reports-archive").mkdir()
        result = action_gateway.execute("search_files", {"query": "report"})
        self.assertIn("[file]", result)
        self.assertIn("[folder]", result)
        self.assertIn(str(document.resolve()), result)
        self.assertNotIn("PRIVATE_BODY_MARKER", result)

    def test_fuzzy_search_matches_typos(self):
        """When an exact match is missing, nearest fuzzy matches are returned."""
        (self.root / "elder people").mkdir()
        (self.root / "action_gateway.py").write_text("code", encoding="utf-8")
        # Typo 1: 'elder peple'
        result1 = action_gateway.execute("search_files", {"query": "elder peple"})
        self.assertIn("Nearest matching result(s)", result1)
        self.assertIn("elder people", result1)
        # Typo 2: 'gatway'
        result2 = action_gateway.execute("search_files", {"query": "gatway"})
        self.assertIn("action_gateway.py", result2)

    def test_search_results_are_bounded(self):
        """The configured result maximum prevents an unbounded result list."""
        for index in range(skills.MAX_FILE_SEARCH_RESULTS + 7):
            (self.root / f"report-{index}.txt").write_text("x", encoding="utf-8")
        result = skills.search_files("report")
        self.assertEqual(len(skills._FILE_SEARCH_RESULTS), skills.MAX_FILE_SEARCH_RESULTS)
        self.assertIn(f"found {skills.MAX_FILE_SEARCH_RESULTS} result(s)", result)

    def test_search_work_is_bounded_and_permission_errors_are_safe(self):
        """Traversal stops at its entry budget and unreadable roots return safely."""
        for index in range(5):
            (self.root / f"item-{index}.txt").write_text("x", encoding="utf-8")
        with patch.object(skills, "MAX_FILE_SEARCH_ENTRIES", 1):
            result = skills.search_files("no-match")
        self.assertIn("safety limit", result)
        with patch("skills.os.scandir", side_effect=PermissionError("private")):
            result = skills.search_files("no-match")
        self.assertIn("could not read some folders", result)

    def test_search_rejects_traversal_and_path_queries(self):
        """A query is a name fragment, not a path to escape the approved root."""
        self.assertIn("plain filename", skills.search_files("..\\outside"))
        self.assertEqual(skills._FILE_SEARCH_RESULTS, [])

    def test_search_does_not_follow_symlink_escape_when_supported(self):
        """A link to an outside directory is skipped instead of traversed."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as outside_dir:
            outside = Path(outside_dir)
            secret_file = outside / "report-secret.txt"
            secret_file.write_text("not read", encoding="utf-8")
            link = self.root / "linked-outside"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("This Windows account cannot create directory symlinks.")
            result = skills.search_files("report")
            self.assertNotIn(str(secret_file), result)
            self.assertEqual(skills._FILE_SEARCH_RESULTS, [])

    def test_configured_root_symlink_is_rejected_when_supported(self):
        """A redirected root is not silently approved by resolving its target."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as target_dir:
            target = Path(target_dir)
            (target / "report-secret.txt").write_text("not read", encoding="utf-8")
            redirected_root = self.root / "redirected-root"
            try:
                redirected_root.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("This Windows account cannot create directory symlinks.")
            with patch.object(config, "FILE_SEARCH_ROOTS", [redirected_root]):
                result = skills.search_files("report")
            self.assertIn("File search is unavailable", result)
            self.assertEqual(skills._FILE_SEARCH_RESULTS, [])

    def test_open_selected_result_asks_for_exact_path_before_opener(self):
        """A numbered current result is shown exactly and opened only after yes."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        prompts = []
        with patch("skills.os.startfile", create=True) as opener:
            result = action_gateway.execute(
                "open_search_result", {"index": 1}, lambda prompt: prompts.append(prompt) or "yes"
            )
        self.assertIn(repr(str(selected.resolve())), prompts[0])
        self.assertIn("Windows launch requested", result)
        opener.assert_called_once_with(str(selected.resolve()))

    def test_open_selected_folder_reports_folder_type(self):
        """Folder search results use the same exact-path approval before opening."""
        selected = self.root / "invoices"
        selected.mkdir()
        skills.search_files("invoice")
        prompts = []
        with patch("skills.os.startfile", create=True) as opener:
            result = action_gateway.execute(
                "open_search_result", {"index": 1}, lambda prompt: prompts.append(prompt) or "yes"
            )
        self.assertIn("this folder", prompts[0])
        self.assertIn("Windows launch requested for this folder", result)
        opener.assert_called_once_with(str(selected.resolve()))

    def test_terminal_commands_search_then_open_latest_numbered_result(self):
        """The user-facing parser binds the numbered open command to the latest search."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        search_reply = router.handle("find file report")
        self.assertIn("1. [file]", search_reply)
        with patch("skills.os.startfile", create=True) as opener:
            open_reply = router.handle("open result 1", lambda prompt: "yes")
        self.assertIn("Windows launch requested", open_reply)
        opener.assert_called_once_with(str(selected.resolve()))

    def test_folder_search_uses_the_same_bounded_name_results(self):
        """Folder-name requests use the local file-search skill without AI planning."""
        (self.root / "Invoices 2026").mkdir()
        result = router.handle("search folders named invoices")
        self.assertIn("[folder]", result)
        self.assertIn("Invoices 2026", result)

    def test_denial_prevents_selected_result_from_opening(self):
        """A no answer leaves the platform opener untouched."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        with patch("skills.os.startfile", create=True) as opener:
            with self.assertRaises(action_gateway.ApprovalDenied):
                action_gateway.execute("open_search_result", {"index": 1}, lambda prompt: "no")
        opener.assert_not_called()

    def test_direct_selected_result_skill_call_is_blocked(self):
        """A valid cached path still cannot be opened without gateway authorization."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        with patch("skills.os.startfile", create=True) as opener:
            with self.assertRaises(PermissionError):
                skills.open_search_result(1)
        opener.assert_not_called()

    def test_missing_or_changed_search_result_is_refused(self):
        """A stale index cannot be replaced by an arbitrary path or opened later."""
        with self.assertRaises(action_gateway.InvalidAction):
            action_gateway.execute("open_search_result", {"index": 1}, lambda prompt: "yes")
        with self.assertRaises(action_gateway.InvalidAction):
            action_gateway.execute("open_search_result", {"index": 1, "path": "C:\\outside.txt"}, lambda prompt: "yes")
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        selected.unlink()
        with self.assertRaises(action_gateway.InvalidAction):
            action_gateway.execute("open_search_result", {"index": 1}, lambda prompt: "yes")

    def test_mocked_windows_open_error_is_reported(self):
        """An OS launch error becomes a clear response and does not escape."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        with patch("skills.os.startfile", create=True, side_effect=OSError("private detail")):
            result = action_gateway.execute("open_search_result", {"index": 1}, lambda prompt: "yes")
        self.assertIn("couldn't request Windows", result)
        self.assertNotIn("private detail", result)

    def test_changed_result_after_approval_is_not_opened(self):
        """A result changed after its prompt fails revalidation before the opener."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")

        def change_result(prompt):
            selected.unlink()
            selected.mkdir()
            return "yes"

        with patch("skills.os.startfile", create=True) as opener:
            result = action_gateway.execute("open_search_result", {"index": 1}, change_result)
        self.assertIn("no longer available", result)
        opener.assert_not_called()

    def test_stale_result_is_reported_as_failed_by_planner(self):
        """A result removed during approval is not summarized as successful."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")

        def remove_during_approval(prompt):
            selected.unlink()
            return "yes"

        step = PlanStep("step_1", "open_search_result", {"index": 1})
        with patch("skills.os.startfile", create=True) as opener:
            task_planner._execute([step], remove_during_approval)
        self.assertEqual(step.status, "failed")
        opener.assert_not_called()

    def test_unsupported_platform_is_reported_as_failed_by_planner(self):
        """Unsupported opening is a failure, not a successful action result."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        step = PlanStep("step_1", "open_search_result", {"index": 1})
        with patch("skills.os.startfile", None, create=True):
            task_planner._execute([step], lambda prompt: "yes")
        self.assertEqual(step.status, "failed")
        self.assertIn("supported only on Windows", step.result)

    def test_opener_exception_is_reported_as_failed_by_planner(self):
        """An OS opener error remains a failed action in the task summary."""
        selected = self.root / "report.txt"
        selected.write_text("contents", encoding="utf-8")
        skills.search_files("report")
        step = PlanStep("step_1", "open_search_result", {"index": 1})
        with patch("skills.os.startfile", create=True, side_effect=OSError("mock failure")):
            task_planner._execute([step], lambda prompt: "yes")
        self.assertEqual(step.status, "failed")
        self.assertTrue(step.result.startswith("I couldn't request Windows to open"))


if __name__ == "__main__":
    unittest.main()
