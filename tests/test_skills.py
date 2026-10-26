"""Tests for local note storage and approved app launch behavior."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import skills


class NoteTests(unittest.TestCase):
    """Check that notes stay inside the project and handle damaged data safely."""

    def test_add_and_show_notes_round_trip(self):
        """A note is stored in project data and shown with its original wording."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            with patch.object(config, "DATA_FOLDER", Path(directory)):
                self.assertEqual(skills.add_note("salt and pepper"), "Note saved.")
                self.assertEqual(skills.show_notes(), "1. salt and pepper")

    def test_corrupt_note_shape_is_not_overwritten(self):
        """Unexpected note entries are reported rather than silently replaced."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            data_folder = Path(directory)
            note_path = data_folder / "notes.json"
            note_path.write_text(json.dumps(["valid", 4]), encoding="utf-8")
            with patch.object(config, "DATA_FOLDER", data_folder):
                self.assertIn("unexpected format", skills.add_note("new note"))
                self.assertIn("unexpected format", skills.show_notes())
            self.assertEqual(json.loads(note_path.read_text(encoding="utf-8")), ["valid", 4])

    def test_redirected_note_path_fails_closed(self):
        """A redirected data path cannot trigger a write."""
        with patch("skills._notes_path_is_safe", return_value=False), patch("skills.tempfile.mkstemp") as create:
            self.assertIn("refused", skills.add_note("private"))
        create.assert_not_called()


class ApprovedAppTests(unittest.TestCase):
    """Check that app launching uses only configured executable paths."""

    def test_configured_app_launch_uses_fixed_path_without_shell(self):
        """Notepad resolves from the allowlist and launches as an argument list."""
        with patch("skills.shutil.which", return_value=r"C:\Windows\notepad.exe"), \
                patch.object(skills.os, "startfile", create=True) as startfile:
            reply = skills.open_approved("notepad")
        self.assertEqual(reply, "Opened notepad.")
        startfile.assert_called_once_with(r"C:\Windows\notepad.exe")

    def test_website_launch_uses_configured_url(self):
        """A website launch opens the URL stored in the fixed allowlist."""
        with patch("skills.webbrowser.open", return_value=True) as open_browser:
            reply = skills.open_approved("youtube")
        self.assertEqual(reply, "Opened youtube.")
        open_browser.assert_called_once_with(config.WEBSITES["youtube"], new=2)

    def test_unapproved_app_never_launches(self):
        """An arbitrary app name cannot become a process command."""
        with patch("skills.subprocess.Popen") as process, patch("skills.os.startfile", create=True) as startfile:
            reply = skills.open_approved("unlisted program")
        self.assertIn("not on Iris's approved", reply)
        process.assert_not_called()
        startfile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
