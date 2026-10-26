"""Tests for keeping the command loop alive after a handler error."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main


class MainLoopTests(unittest.TestCase):
    """Check the terminal loop reports errors and accepts another command."""

    def test_handler_error_does_not_end_the_loop_or_log_exception_text(self):
        """A failed request is reported safely and the next command still runs."""
        output = io.StringIO()
        with patch("main.setup_logging"), \
                patch("builtins.input", side_effect=["first", "exit"]), \
                patch("main.router.handle", side_effect=[RuntimeError("private detail"), "Goodbye!"]), \
                patch("main.logging.error") as log_error, redirect_stdout(output):
            main.run()
        self.assertIn("Iris is still running", output.getvalue())
        self.assertIn("Goodbye!", output.getvalue())
        self.assertEqual(log_error.call_args.args, ("request failed; error_type=%s", "RuntimeError"))


if __name__ == "__main__":
    unittest.main()
