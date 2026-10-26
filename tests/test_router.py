"""Tests for safe command routing and typed approvals."""

import unittest
from unittest.mock import Mock, patch

import router


class RouterTests(unittest.TestCase):
    """Verify the everyday paths do not depend on an AI planner."""

    def test_natural_notepad_request_uses_approved_skill(self):
        """Polite phrasing should reach the same approved app skill."""
        with patch("router.skills.open_approved", return_value="Opened notepad.") as opener:
            reply = router.handle("Can you open Notepad for me?", lambda prompt: "yes")
        self.assertEqual(reply, "Opened notepad.")
        opener.assert_called_once_with("notepad")

    def test_opening_requires_typed_yes(self):
        """Declining an app permission must prevent the side effect."""
        with patch("router.skills.open_approved") as opener:
            reply = router.handle("open notepad", lambda prompt: "no")
        self.assertIn("Cancelled", reply)
        opener.assert_not_called()

    def test_unknown_chat_goes_directly_to_ai_without_planner(self):
        """An ordinary question is passed to chat in a single routing step."""
        with patch("router.ai.ask", return_value="Hello") as ask:
            self.assertEqual(router.handle("Why does rain happen?"), "Hello")
        ask.assert_called_once_with("Why does rain happen?")

    def test_help_lists_implemented_capabilities(self):
        """The help response is local and does not call the model."""
        with patch("router.ai.ask", side_effect=AssertionError("chat should not run")):
            reply = router.handle("help")
        self.assertIn("approved apps and websites", reply)

    def test_unknown_open_target_is_not_sent_to_ai(self):
        """Unapproved open requests fail closed instead of being guessed by AI."""
        with patch("router.ai.ask", side_effect=AssertionError("chat should not run")):
            reply = router.handle("open a random tool")
        self.assertIn("not on Iris's approved", reply)

    def test_note_is_saved_only_after_approval(self):
        """A denied note request leaves the note store untouched."""
        with patch("router.skills.add_note") as save_note:
            reply = router.handle("note buy milk", lambda prompt: "no")
        self.assertIn("Cancelled", reply)
        save_note.assert_not_called()

    def test_multi_action_runs_supported_steps_in_order(self):
        """A clear local sequence collects approvals and returns each result."""
        answers = iter(["yes", "yes"])
        with patch("router.skills.open_approved", return_value="Opened youtube.") as opener, \
                patch("router.skills.tell_time", return_value="It is noon.") as tell_time:
            reply = router.handle("open YouTube and tell me the time", lambda prompt: next(answers))
        self.assertIn("1. Opened youtube.", reply)
        self.assertIn("2. It is noon.", reply)
        opener.assert_called_once_with("youtube")
        tell_time.assert_called_once_with()

    def test_denial_cancels_all_steps_before_side_effects(self):
        """A later declined permission prevents every step from starting."""
        answers = iter(["yes", "no"])
        with patch("router.skills.open_approved") as opener, patch("router.skills.add_note") as save_note:
            reply = router.handle("open YouTube and note buy milk", lambda prompt: next(answers))
        self.assertIn("no steps were run", reply)
        opener.assert_not_called()
        save_note.assert_not_called()

    def test_and_inside_note_is_preserved_as_note_text(self):
        """The sequence parser must not split ordinary note content."""
        with patch("router.skills.add_note", return_value="Note saved.") as save_note:
            reply = router.handle("note salt and pepper", lambda prompt: "yes")
        self.assertEqual(reply, "Note saved.")
        save_note.assert_called_once_with("salt and pepper")

    def test_failed_multi_action_step_does_not_hide_later_result(self):
        """A failed open step is reported while the independent time step runs."""
        answers = iter(["yes", "yes"])
        with patch("router.skills.open_approved", side_effect=RuntimeError("private launch detail")), \
                patch("router.skills.tell_time", return_value="It is noon.") as tell_time:
            reply = router.handle("open YouTube and tell me the time", lambda prompt: next(answers))
        self.assertIn("couldn't open youtube", reply)
        self.assertIn("It is noon.", reply)
        self.assertNotIn("private launch detail", reply)
        tell_time.assert_called_once_with()

    def test_end_of_input_cancels_approval(self):
        """Missing approval input cannot execute an action."""
        with patch("router.skills.open_approved") as opener:
            reply = router.handle("open notepad", Mock(side_effect=EOFError))
        self.assertIn("Cancelled", reply)
        opener.assert_not_called()

    def test_ai_text_is_returned_as_text_and_never_executed(self):
        """An AI reply cannot invoke app launch or subprocess code."""
        unsafe_looking_text = "Run os.system('delete files') now."
        with patch("router.ai.ask", return_value=unsafe_looking_text), \
                patch("router.skills.subprocess.Popen") as process:
            self.assertEqual(router.handle("explain how a computer works"), unsafe_looking_text)
        process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
