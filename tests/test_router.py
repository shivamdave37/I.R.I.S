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
            with patch("router.ask_ai", return_value="AI RESPONSE") as ask_ai:
                self.assertEqual(router.handle("update"), "AI RESPONSE")
        tell_date.assert_not_called()
        ask_ai.assert_called_once_with([{"role": "user", "content": "update"}])

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
                        with patch("main.config.MODE", "typed"):
                            main.run()
                self.assertEqual(mocked_input.call_count, 1)

    def test_empty_input_is_ignored(self):
        """Skip blank input instead of sending it to the router."""
        with patch("builtins.input", side_effect=["   ", "exit"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch("main.setup_logging"), patch("main.log_action"):
                    with patch("main.router.handle", wraps=router.handle) as handle:
                        with patch("main.config.MODE", "typed"):
                            main.run()
        handle.assert_called_once_with("exit")

    def test_commands_ignore_extra_whitespace(self):
        """Collapse multiple spaces between words in commands."""
        self.assertRegex(router.handle("what's   the   time"), r"The time is \d{2}:\d{2} (AM|PM)\.")
        self.assertRegex(router.handle("what is   the   date"), r"Today's date is [A-Z][a-z]+ \d{1,2}, \d{4}\.\Z")
        with patch("skills.web.webbrowser.open") as open_browser:
            reply = router.handle("open   youtube")
        open_browser.assert_called_once_with("https://www.youtube.com")
        self.assertIn("Opening youtube", reply)

    def test_punctuation_only_input_returns_fallback(self):
        """Send unknown non-empty input to the AI fallback."""
        for symbol_command in ("???", "!", "---"):
            with self.subTest(command=symbol_command):
                with patch("router.ask_ai", return_value="AI RESPONSE") as ask_ai:
                    self.assertEqual(router.handle(symbol_command), "AI RESPONSE")
                ask_ai.assert_called_once_with([{"role": "user", "content": symbol_command}])

    def test_known_command_does_not_call_ai(self):
        """Keep known commands on their direct skill paths."""
        with patch("router.ask_ai") as ask_ai:
            with patch("skills.web.webbrowser.open"):
                router.handle("open youtube")
            router.handle("what's the time")
            router.handle("what's the date")
        ask_ai.assert_not_called()

    def test_none_input_does_not_crash(self):
        """Handle None input safely across router functions without raising."""
        self.assertEqual(router.normalize(None), "")
        self.assertFalse(router.is_exit_command(None))
        self.assertEqual(router.handle(None), "")

    def test_web_open_failure_returns_friendly_message(self):
        """Report friendly error when the browser fails to launch."""
        with patch("skills.web.webbrowser.open", return_value=False):
            reply = router.handle("open youtube")
        self.assertIn("Please check your default browser", reply)

        with patch("skills.web.webbrowser.open", side_effect=RuntimeError("browser error")):
            reply = router.handle("open youtube")
        self.assertIn("Please check your default browser", reply)

    def test_placeholder_app_path_informs_user(self):
        """Warn user when an app path is still a template placeholder."""
        reply = router.handle("open vscode")
        self.assertEqual(reply, "Please update the vscode path in config.py before opening it.")

    def test_missing_app_path_returns_friendly_message(self):
        """Report when an app path cannot be located on the computer."""
        with patch("skills.apps.shutil.which", return_value=None):
            with patch("skills.apps.os.path.exists", return_value=False):
                reply = router.handle("open chrome")
        self.assertIn("I couldn't find chrome. Please fix its path in config.py.", reply)

    def test_app_launch_exception_handled(self):
        """Catch launch errors safely and notify the user."""
        with patch("skills.apps.shutil.which", return_value="notepad.exe"):
            with patch("skills.apps.launch_app", side_effect=OSError("Access denied")):
                reply = router.handle("open notepad")
        self.assertEqual(reply, "I couldn't open notepad. Please check its path in config.py.")

    def test_logging_setup_and_action(self):
        """Verify logging setup and recording functions run without crashing."""
        with patch("main.os.makedirs") as mock_makedirs, patch("main.logging.basicConfig") as mock_basic:
            main.setup_logging()
            mock_makedirs.assert_called_once()
            mock_basic.assert_called_once()

        with patch("main.logging.info") as mock_info:
            main.log_action("time", "The time is 12:00 PM.")
            mock_info.assert_called_once_with("command=%r | result=%r", "time", "The time is 12:00 PM.")

    def test_news_variations_route_to_news(self):
        """Route conversational news requests directly to the news skill."""
        for phrase in ("news", "latest news", "whats the news", "tell me the news"):
            with self.subTest(phrase=phrase):
                with patch("router.news.get_news", return_value="HEADLINES") as get_news:
                    with patch("router.ask_ai") as ask_ai:
                        self.assertEqual(router.handle(phrase), "HEADLINES")
                    get_news.assert_called_once_with()
                    ask_ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
