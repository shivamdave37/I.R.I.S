"""End-to-end checks for the real terminal loop with isolated side effects."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import uuid

import config
import main
import router
import skills


class PhaseFiveIntegrationTests(unittest.TestCase):
    """Exercise startup, routing, notes, denied actions, and clean exit together."""

    def test_terminal_workflow_uses_temp_notes_and_denies_side_effects(self):
        """The live loop preserves a note after denied delete and multi-step requests."""
        commands = [
            "help",
            "note phase5 marker",
            "yes",
            "search notes for phase5 marker",
            "delete note 1",
            "no",
            "search notes for phase5 marker",
            "open YouTube and note should not be saved",
            "no",
            "search notes for phase5 marker",
            "exit",
        ]
        output = io.StringIO()
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            note_folder = Path(directory) / "data"
            with patch.object(config, "DATA_FOLDER", note_folder), \
                    patch("main.setup_logging"), \
                    patch("skills.open_approved") as open_app, \
                    patch("sys.stdin", io.StringIO("\n".join(commands) + "\n")), \
                    redirect_stdout(output):
                main.run()
            self.assertEqual(json.loads((note_folder / "notes.json").read_text(encoding="utf-8")), ["phase5 marker"])
        open_app.assert_not_called()
        transcript = output.getvalue()
        self.assertIn("Iris is ready", transcript)
        self.assertIn("Note saved.", transcript)
        self.assertGreaterEqual(transcript.count("1. phase5 marker"), 3)
        self.assertIn("Cancelled; no steps were run.", transcript)
        self.assertIn("Goodbye!", transcript)

    def test_denied_open_and_note_plan_does_not_persist_unique_marker(self):
        """Denying the first approval skips note saving in a fresh note store."""
        marker = "IRIS_MULTI_DENY_REPRO_" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            note_folder = Path(directory) / "data"
            output = io.StringIO()
            with patch.object(config, "DATA_FOLDER", note_folder), \
                    patch("skills.open_approved") as open_app, \
                    redirect_stdout(output):
                reply = router.handle(
                    f"open Notepad and note {marker}",
                    lambda prompt: "no",
                )
                search_reply = skills.search_notes(marker)
            self.assertIn("open_target [denied]", reply)
            self.assertIn("save_note [skipped]", reply)
            self.assertIn("Cancelled; no steps were run.", reply)
            self.assertEqual(search_reply, "No matching notes.")
            self.assertFalse((note_folder / "notes.json").exists())
        open_app.assert_not_called()


if __name__ == "__main__":
    unittest.main()
