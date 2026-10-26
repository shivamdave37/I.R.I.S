"""Tests for direct AI chat routing and temporary history behavior."""

import unittest
import os
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import ai
import config


class AiTests(unittest.TestCase):
    """Check chat fallback is direct and handles unconfigured providers clearly."""

    def setUp(self):
        """Start every test with empty conversation state."""
        ai.clear_history()

    def tearDown(self):
        """Avoid carrying test messages into another test."""
        ai.clear_history()

    def test_gemini_question_uses_one_model_request(self):
        """A question reaches one provider call without a planning stage."""
        with patch("ai._ask_gemini", return_value=(True, "Answer")) as ask:
            self.assertEqual(ai.ask("Hi"), "Answer")
        ask.assert_called_once()

    def test_provider_failure_is_clear_and_not_kept_in_history(self):
        """Failed calls return a useful message and do not pollute later context."""
        with patch("ai._ask_gemini", return_value=(False, "I couldn't reach Gemini.")):
            reply = ai.ask("question")
        self.assertIn("couldn't reach Gemini", reply)
        self.assertEqual(ai._HISTORY, [])

    def test_unknown_provider_does_not_call_a_model(self):
        """Invalid provider settings are rejected locally."""
        with patch.dict("os.environ", {"IRIS_AI_PROVIDER": "other"}), patch("ai._ask_gemini") as gemini:
            self.assertIn("Unknown AI provider", ai.ask("hi"))
        gemini.assert_not_called()

    def test_gemini_maps_assistant_role_to_model_and_keeps_key_out_of_url(self):
        """Gemini receives API-supported history roles and the key in a header."""
        response = {"candidates": [{"content": {"parts": [{"text": "First reply"}]}}]}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-secret", "IRIS_AI_PROVIDER": "gemini"}), \
                patch("ai._request_json", return_value=response) as request:
            self.assertEqual(ai.ask("hello"), "First reply")
            ai.ask("follow up")
        url, payload, headers = request.call_args.args
        roles = [item["role"] for item in payload["contents"]]
        self.assertEqual(roles, ["user", "model", "user"])
        self.assertNotIn("test-secret", url)
        self.assertEqual(headers["x-goog-api-key"], "test-secret")

    def test_missing_gemini_key_is_clear_and_does_not_call_network(self):
        """A missing key is reported before an HTTP request is attempted."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "IRIS_AI_PROVIDER": "gemini"}), \
                patch("ai._request_json") as request:
            reply = ai.ask("hello")
        self.assertIn("not configured", reply)
        request.assert_not_called()

    def test_configured_key_in_chat_is_not_sent_to_provider(self):
        """A pasted configured credential is rejected before the AI call."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-value", "IRIS_AI_PROVIDER": "gemini"}), \
                patch("ai._ask_gemini") as ask_gemini:
            reply = ai.ask("Here is my key: secret-value")
        self.assertIn("can't send", reply)
        ask_gemini.assert_not_called()
        self.assertEqual(ai._HISTORY, [])

    def test_gemini_rate_limit_has_a_specific_message(self):
        """HTTP 429 is explained as a provider rate limit without exposing its body."""
        error = urllib.error.HTTPError("https://example.invalid", 429, "quota", {}, None)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "key", "IRIS_AI_PROVIDER": "gemini"}), \
                patch("ai._request_json", side_effect=error):
            reply = ai.ask("hello")
        self.assertIn("rate limit", reply)
        self.assertNotIn("quota", reply.lower())

    def test_ollama_refuses_non_loopback_service(self):
        """Ollama chat text is never sent to an internet host by configuration."""
        with patch.dict(os.environ, {"IRIS_AI_PROVIDER": "ollama"}), \
                patch("ai.config.OLLAMA_URL", "http://example.com/api/chat"), \
                patch("ai._request_json") as request:
            reply = ai.ask("private question")
        self.assertIn("local loopback", reply)
        request.assert_not_called()

    def test_ollama_missing_service_has_a_clear_message(self):
        """A local connection failure is reported without raising an exception."""
        with patch.dict(os.environ, {"IRIS_AI_PROVIDER": "ollama"}), \
                patch("ai._request_json", side_effect=urllib.error.URLError("offline")):
            reply = ai.ask("hello")
        self.assertIn("Start Ollama", reply)

    def test_successful_ai_reply_that_looks_like_error_is_still_chat(self):
        """Provider status comes from the result flag, not the reply wording."""
        with patch("ai._ask_gemini", return_value=(True, "I couldn't agree more.")):
            reply = ai.ask("Do you agree?")
        self.assertEqual(reply, "I couldn't agree more.")
        self.assertEqual(ai._HISTORY[-1]["role"], "assistant")

    def test_provider_setting_is_loaded_before_provider_selection(self):
        """An Ollama choice in the local env file affects the same request."""
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            Path(directory, ".env").write_text(
                "IRIS_AI_PROVIDER=ollama\nUNEXPECTED_SETTING=ignored\n", encoding="utf-8"
            )
            with patch.object(ai.config, "PROJECT_FOLDER", Path(directory)), \
                    patch.dict(os.environ, {}, clear=True), \
                    patch("ai._ask_ollama", return_value=(True, "Local reply")) as ask_ollama:
                self.assertEqual(ai.ask("hello"), "Local reply")
                self.assertNotIn("UNEXPECTED_SETTING", os.environ)
            ask_ollama.assert_called_once()

    def test_http_request_has_a_finite_timeout(self):
        """External service requests cannot wait forever."""
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"{}"
        with patch("ai.urllib.request.urlopen", return_value=response) as open_url:
            self.assertEqual(ai._request_json("https://example.invalid", {}), {})
        self.assertEqual(open_url.call_args.kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
