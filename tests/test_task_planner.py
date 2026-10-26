"""Tests for task-plan validation, safe execution, and note management."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import config
import skills
import task_planner


class PlanValidationTests(unittest.TestCase):
    """Check that only fixed skills and exact parameter schemas are accepted."""

    def test_valid_ordered_plan_has_explicit_step_status(self):
        """A well-formed plan becomes structured steps with pending states."""
        plan = task_planner.validate_plan({"steps": [
            {"id": "step_1", "skill": "tell_time", "params": {}, "depends_on": []},
            {"id": "step_2", "skill": "save_note", "params": {"text": "study"}, "depends_on": ["step_1"]},
        ]})
        self.assertEqual([step.status for step in plan], ["pending", "pending"])
        self.assertEqual(plan[1].depends_on, ["step_1"])
        self.assertEqual(plan[1].permission, "save this note")

    def test_unregistered_skill_is_rejected(self):
        """A model cannot add an executable skill by naming it in JSON."""
        payload = {"steps": [{"id": "step_1", "skill": "run_shell", "params": {}, "depends_on": []}]}
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            task_planner.validate_plan(payload)

    def test_invalid_parameters_and_later_dependencies_are_rejected(self):
        """Unknown parameters and forward dependencies fail before execution."""
        invalid_params = {"steps": [{"id": "step_1", "skill": "tell_time", "params": {"command": "x"}, "depends_on": []}]}
        forward_dependency = {"steps": [{"id": "step_1", "skill": "tell_time", "params": {}, "depends_on": ["step_2"]}]}
        with self.assertRaisesRegex(ValueError, "Invalid parameters"):
            task_planner.validate_plan(invalid_params)
        with self.assertRaisesRegex(ValueError, "earlier steps"):
            task_planner.validate_plan(forward_dependency)

    def test_unapproved_targets_are_rejected(self):
        """A plan target must be present in the local allowlist."""
        payload = {"steps": [{"id": "step_1", "skill": "open_target", "params": {"target": "powershell"}, "depends_on": []}]}
        with self.assertRaisesRegex(ValueError, "approved app or website"):
            task_planner.validate_plan(payload)

    def test_note_parameter_limit_is_checked_before_plan_execution(self):
        """Oversized local notes are rejected before Iris asks permission or writes."""
        with patch("skills.add_note") as save_note:
            reply = task_planner.handle("note " + ("x" * (task_planner.MAX_NOTE_LENGTH + 1)))
        self.assertIn("No steps were run", reply)
        save_note.assert_not_called()


class PlanExecutionTests(unittest.TestCase):
    """Check preview, approvals, per-step failure, and dependency behavior."""

    def test_comma_separated_known_actions_run_in_order(self):
        """A supported three-step request is planned locally and executed in order."""
        answers = iter(["yes", "yes"])
        output = io.StringIO()
        with patch("skills.open_approved", return_value="Opened youtube.") as opener, \
                patch("skills.tell_time", return_value="It is noon.") as time_skill, \
                patch("skills.add_note", return_value="Note saved.") as note_skill, \
                redirect_stdout(output):
            reply = task_planner.handle(
                "Open YouTube, tell me the time, and save a note to study Python tomorrow.",
                lambda prompt: next(answers),
            )
        self.assertIn("open_target", output.getvalue())
        self.assertIn("Finished: 3 succeeded", reply)
        opener.assert_called_once_with("youtube")
        time_skill.assert_called_once_with()
        note_skill.assert_called_once_with("to study Python tomorrow.")

    def test_denial_prevents_every_step(self):
        """Approvals are collected before any side effect begins."""
        output = io.StringIO()
        with patch("skills.open_approved") as opener, patch("skills.add_note") as save_note, redirect_stdout(output):
            reply = task_planner.handle("open YouTube and note buy milk", lambda prompt: "no")
        self.assertIn("Cancelled", reply)
        opener.assert_not_called()
        save_note.assert_not_called()

    def test_approved_delete_reaches_guarded_note_function(self):
        """After typed approval the executor passes the approval guard explicitly."""
        output = io.StringIO()
        with patch("skills.delete_note", return_value="Deleted note 1: buy milk") as delete_note, redirect_stdout(output):
            reply = task_planner.handle("delete note 1", lambda prompt: "yes")
        self.assertEqual(reply, "Deleted note 1: buy milk")
        delete_note.assert_called_once_with(1, approved=True)

    def test_failed_step_skips_dependent_but_runs_independent_step(self):
        """Only steps requiring a failed result are skipped."""
        plan = task_planner.validate_plan({"steps": [
            {"id": "step_1", "skill": "open_target", "params": {"target": "youtube"}, "depends_on": []},
            {"id": "step_2", "skill": "save_note", "params": {"text": "after open"}, "depends_on": ["step_1"]},
            {"id": "step_3", "skill": "tell_time", "params": {}, "depends_on": []},
        ]})
        answers = iter(["yes", "yes"])
        with patch("skills.open_approved", side_effect=RuntimeError("private detail")), \
                patch("skills.add_note") as save_note, \
                patch("skills.tell_time", return_value="It is noon.") as tell_time:
            result = task_planner._execute(plan, lambda prompt: next(answers))
        self.assertEqual([step.status for step in plan], ["failed", "skipped", "succeeded"])
        self.assertIn("Skipped because a required step", result)
        self.assertNotIn("private detail", result)
        save_note.assert_not_called()
        tell_time.assert_called_once_with()

    def test_model_plan_with_unregistered_action_fails_closed(self):
        """Unsafe model JSON is rejected before opening an app or running code."""
        unsafe = json.dumps({"steps": [
            {"id": "step_1", "skill": "shell", "params": {"command": "whoami"}, "depends_on": []}
        ]})
        output = io.StringIO()
        with patch("task_planner.ai.plan_request", return_value=unsafe), \
                patch("skills.subprocess.Popen") as process, redirect_stdout(output):
            reply = task_planner.handle("help me coordinate my workflow", lambda prompt: "yes")
        self.assertIn("No steps were run", reply)
        process.assert_not_called()

    def test_research_and_note_are_not_silently_combined(self):
        """Research output must be inspected before a user-selected note is saved."""
        payload = {"steps": [
            {"id": "step_1", "skill": "research_web", "params": {"query": "Python testing"}, "depends_on": []},
            {"id": "step_2", "skill": "save_note", "params": {"text": "AI invented findings"}, "depends_on": ["step_1"]},
        ]}
        with self.assertRaisesRegex(ValueError, "Inspect the research report first"):
            task_planner.validate_plan(payload)


class NoteSearchDeleteTests(unittest.TestCase):
    """Check keyword search and confirmed deletion in isolated note storage."""

    def test_search_and_delete_selected_note(self):
        """Search is case-insensitive and deletion changes only the chosen note."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            with patch.object(config, "DATA_FOLDER", Path(directory)):
                skills.add_note("Study Python tomorrow")
                skills.add_note("Buy milk")
                self.assertEqual(skills.search_notes("PYTHON"), "1. Study Python tomorrow")
                self.assertIn("confirmation", skills.delete_note(1).lower())
                self.assertEqual(skills.delete_note(1, approved=True), "Deleted note 1: Study Python tomorrow")
                self.assertEqual(skills.show_notes(), "1. Buy milk")

    def test_invalid_delete_index_preserves_notes(self):
        """A missing selection cannot delete or rewrite the note list."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            with patch.object(config, "DATA_FOLDER", Path(directory)):
                skills.add_note("keep me")
                self.assertIn("does not exist", skills.delete_note(2, approved=True))
                self.assertEqual(skills.show_notes(), "1. keep me")


if __name__ == "__main__":
    unittest.main()
