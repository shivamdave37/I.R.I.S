"""Tests for inert skill proposals and their approval/audit workflow."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import config
import skill_development


VALID_SOURCE = '''def skill_greeting(request):
    """Return a short greeting from a request."""
    return "Hello " + str(request)
'''


class ProposalValidationTests(unittest.TestCase):
    """Check metadata and source constraints without executing proposed code."""

    def test_simple_pure_proposal_passes_static_checks(self):
        """A one-function source file inside the restricted subset is accepted."""
        result = skill_development.validate_proposal("greeting", "Return a short greeting", VALID_SOURCE)
        self.assertIn("Static checks passed", result)

    def test_imports_process_access_and_invalid_metadata_are_rejected(self):
        """Proposal validation rejects dangerous syntax and bad names."""
        import_source = "import os\n" + VALID_SOURCE
        process_source = VALID_SOURCE.replace('return "Hello "', 'return open("file").read() or "Hello "')
        with self.assertRaisesRegex(ValueError, "exactly one top-level"):
            skill_development.validate_proposal("greeting", "Return a short greeting", import_source)
        with self.assertRaisesRegex(ValueError, "Disallowed Python syntax|Disallowed name|fixed pure built-in"):
            skill_development.validate_proposal("greeting", "Return a short greeting", process_source)
        with self.assertRaisesRegex(ValueError, "simple skill name"):
            skill_development.validate_proposal("../bad", "Return a short greeting", VALID_SOURCE)

    def test_invalid_python_is_not_validated_or_executed(self):
        """Malformed candidate source stops at ast.parse and never runs."""
        with self.assertRaisesRegex(ValueError, "syntax check failed"):
            skill_development.validate_proposal("greeting", "Return a short greeting", "def skill_greeting(:")


class ProposalWorkflowTests(unittest.TestCase):
    """Check typed save approval, persistence, review, and reversible withdrawal."""

    def run_with_temp_proposals(self, callback):
        """Give each workflow test an isolated proposal folder inside the project."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            proposal_folder = Path(directory) / "skill_proposals"
            with patch.object(skill_development, "PROPOSALS_FOLDER", proposal_folder):
                callback(proposal_folder)

    def test_valid_draft_is_displayed_then_saved_as_inert_version(self):
        """The exact candidate and static result are shown before typed save approval."""
        def exercise(folder):
            output = StringIO()
            with patch("skill_development.ai.generate_skill_proposal", return_value=VALID_SOURCE), redirect_stdout(output):
                result = skill_development.create_proposal("greeting", "Return a short greeting", lambda prompt: "yes")
            self.assertIn("not active", result)
            self.assertIn("NOT RUN", output.getvalue())
            self.assertIn("def skill_greeting", output.getvalue())
            record = json.loads((folder / "greeting-v001.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "awaiting human code review; not active")
            self.assertIn("proposal_saved", (folder / "events.jsonl").read_text(encoding="utf-8"))
        self.run_with_temp_proposals(exercise)

    def test_denied_save_leaves_no_proposal_file(self):
        """Declining the post-preview approval prevents proposal persistence."""
        def exercise(folder):
            with patch("skill_development.ai.generate_skill_proposal", return_value=VALID_SOURCE), redirect_stdout(StringIO()):
                result = skill_development.create_proposal("greeting", "Return a short greeting", lambda prompt: "no")
            self.assertIn("denied", result.lower())
            self.assertFalse(folder.exists())
        self.run_with_temp_proposals(exercise)

    def test_failed_static_validation_does_not_save_generated_code(self):
        """Generated imports fail validation before a permission prompt or file write."""
        unsafe = "import os\ndef skill_greeting(request):\n    \"\"\"Return a greeting.\"\"\"\n    return str(request)"
        def exercise(folder):
            with patch("skill_development.ai.generate_skill_proposal", return_value=unsafe):
                result = skill_development.create_proposal("greeting", "Return a short greeting", lambda prompt: "yes")
            self.assertIn("validation failed", result.lower())
            self.assertFalse(folder.exists())
        self.run_with_temp_proposals(exercise)

    def test_manual_approval_is_recorded_but_never_activates_code(self):
        """Typed approval records intent but leaves the static registry untouched."""
        def exercise(folder):
            with patch("skill_development.ai.generate_skill_proposal", return_value=VALID_SOURCE), redirect_stdout(StringIO()):
                skill_development.create_proposal("greeting", "Return a short greeting", lambda prompt: "yes")
                result = skill_development.approve_for_manual_integration("greeting", 1, lambda prompt: "yes")
            self.assertIn("remains inactive", result)
            events = (folder / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn("approved_for_manual_integration", events)
            record = skill_development.read_proposal("greeting", 1)
            self.assertIn("not active", record["status"])
        self.run_with_temp_proposals(exercise)

    def test_withdrawal_records_rollback_without_erasing_history(self):
        """A withdrawn proposal remains available as a versioned audit record."""
        def exercise(folder):
            with patch("skill_development.ai.generate_skill_proposal", return_value=VALID_SOURCE), redirect_stdout(StringIO()):
                skill_development.create_proposal("greeting", "Return a short greeting", lambda prompt: "yes")
                result = skill_development.withdraw_proposal("greeting", 1, lambda prompt: "yes")
            self.assertIn("record remains available", result)
            self.assertTrue((folder / "greeting-v001.json").is_file())
            self.assertIn("proposal_withdrawn", (folder / "events.jsonl").read_text(encoding="utf-8"))
        self.run_with_temp_proposals(exercise)

    def test_tampered_proposal_fails_revalidation(self):
        """A saved proposal changed after validation cannot pass later review."""
        def exercise(folder):
            with patch("skill_development.ai.generate_skill_proposal", return_value=VALID_SOURCE), redirect_stdout(StringIO()):
                skill_development.create_proposal("greeting", "Return a short greeting", lambda prompt: "yes")
            path = folder / "greeting-v001.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["source"] = "import os"
            path.write_text(json.dumps(record), encoding="utf-8")
            self.assertIsNone(skill_development.read_proposal("greeting", 1))
        self.run_with_temp_proposals(exercise)


if __name__ == "__main__":
    unittest.main()
