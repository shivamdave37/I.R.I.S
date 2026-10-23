"""Tests for Stage 1 command routing and the typed loop."""

import io
import unittest
from unittest.mock import patch

import main
import router
from skills import apps


class RouterTests(unittest.TestCase):
    """Check that commands reach only the intended Stage 1 handlers."""

    def test_open_youtube_calls_approved_website(self):
        """Open the configured YouTube URL for a normal command."""
        with patch("skills.web.webbrowser.open") as open_browser:
            reply = router.handle("open youtube")
        open_browser.assert_called_once_with("https://www.youtube.com")
        self.assertIn("Opening youtube", reply)

    def test_open_youtube_ignores_case_and_punctuation(self):
        """Normalize capitals and punctuation before matching."""
        with patch("skills.web.webbrowser.open") as open_browser:
            reply = router.handle("OPEN YouTube!")
        open_browser.assert_called_once_with("https://www.youtube.com")
        self.assertIn("Opening youtube", reply)

    def test_open_approved_app_uses_launcher(self):
        """Use the application launcher only for a configured app."""
        with patch("skills.apps.shutil.which", return_value="notepad.exe"):
            with patch("skills.apps.launch_app") as launch:
                reply = router.handle("open notepad")
        launch.assert_called_once_with("notepad.exe")
        self.assertIn("Opening notepad", reply)

    def test_time_and_date_replies_have_expected_formats(self):
        """Return recognizable time and date text for common questions."""
        self.assertRegex(router.handle("what's the time"), r"The time is \d{2}:\d{2} (AM|PM)\.")
        self.assertRegex(router.handle("what's the date"), r"Today's date is [A-Z][a-z]+ \d{1,2}, \d{4}\.\Z")

    def test_update_does_not_trigger_date(self):
        """Avoid substring matching that mistakes update for a date command."""
        with patch("router.timeinfo.tell_date", return_value="DATE SKILL") as tell_date:
            self.assertEqual(router.handle("update"), "I don't know that yet.")
        tell_date.assert_not_called()

    def test_unknown_app_is_refused(self):
        """Do not pass unapproved names to the application launcher."""
        with patch("skills.apps.launch_app") as launch:
            reply = router.handle("open unknownapp")
        launch.assert_not_called()
        self.assertIn("not on the approved list", reply)

    def test_exit_words_stop_the_loop(self):
        """Stop after exit or quit without reading another command."""
        for word in ("exit", "quit"):
            with self.subTest(word=word):
                command_input = patch("builtins.input", side_effect=[word, "should not run"])
                with command_input as mocked_input, patch("sys.stdout", new_callable=io.StringIO):
                    with patch("main.setup_logging"), patch("main.log_action"):
                        main.run()
                self.assertEqual(mocked_input.call_count, 1)

    def test_empty_input_is_ignored(self):
        """Skip blank input instead of sending it to the router."""
        with patch("builtins.input", side_effect=["   ", "exit"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch("main.setup_logging"), patch("main.log_action"):
                    with patch("main.router.handle", wraps=router.handle) as handle:
                        main.run()
        handle.assert_called_once_with("exit")


if __name__ == "__main__":
    unittest.main()
