"""Tests for AI provider selection and chat history without network calls."""

import unittest
from unittest.mock import Mock, patch

import ai
import config


class AiTests(unittest.TestCase):
    """Check AI replies and privacy behavior using mocked providers."""

    def setUp(self):
        """Clear shared chat state so every test starts with a fresh conversation."""
        ai.CHAT_HISTORY.clear()

    def test_gemini_provider_returns_text(self):
        """Send conversation text to Gemini and return its response."""
        client = Mock()
        client.models.generate_content.return_value.text = "Hello from Gemini."
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.config.AI_FALLBACK_PROVIDER", None):
                with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="fake-key"):
                    with patch("ai.genai.Client", return_value=client) as make_client:
                        reply = ai.ask_ai([{"role": "user", "content": "hello"}])
        self.assertEqual(reply, "Hello from Gemini.")
        make_client.assert_called_once_with(api_key="fake-key")
        self.assertIn("helpful, concise assistant", client.models.generate_content.call_args.kwargs["contents"])

    def test_ollama_provider_returns_text(self):
        """Send chat messages to the configured local Ollama endpoint."""
        response = Mock()
        response.json.return_value = {"message": {"content": "Hello from Ollama."}}
        with patch("ai.config.AI_PROVIDER", "ollama"):
            with patch("ai.config.AI_FALLBACK_PROVIDER", None):
                with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value=None):
                    with patch("ai.requests.post", return_value=response) as post:
                        reply = ai.ask_ai("hello")
        self.assertEqual(reply, "Hello from Ollama.")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], config.OLLAMA_URL)

    def test_chat_history_keeps_only_last_ten_messages(self):
        """Keep the latest ten user and assistant messages after successful turns."""
        client = Mock()
        client.models.generate_content.return_value.text = "A reply."
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.config.AI_FALLBACK_PROVIDER", None):
                with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="fake-key"):
                    with patch("ai.genai.Client", return_value=client):
                        for number in range(1, 7):
                            ai.ask_ai(f"Question {number}")
        self.assertEqual(len(ai.CHAT_HISTORY), 10)
        self.assertEqual(ai.CHAT_HISTORY[0], {"role": "user", "content": "Question 2"})
        self.assertEqual(ai.CHAT_HISTORY[-1], {"role": "assistant", "content": "A reply."})

    def test_missing_gemini_key_returns_clear_message(self):
        """Explain when Gemini is selected without an API key."""
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value=None):
                with patch("ai.genai.Client") as make_client:
                    reply = ai.ask_ai("hello")
        self.assertIn("GEMINI_API_KEY is missing", reply)
        make_client.assert_not_called()

    def test_rate_limit_returns_clear_message_without_fallback(self):
        """Explain quota errors when no alternate provider is configured."""
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED quota")
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.config.AI_FALLBACK_PROVIDER", None):
                with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="fake-key"):
                    with patch("ai.genai.Client", return_value=client):
                        reply = ai.ask_ai("hello")
        self.assertIn("free-tier rate or quota limit", reply)

    def test_rate_limit_uses_configured_fallback_provider(self):
        """Try the configured Ollama provider after Gemini quota exhaustion."""
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError("429 quota exceeded")
        response = Mock()
        response.json.return_value = {"message": {"content": "Local fallback answer."}}
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.config.AI_FALLBACK_PROVIDER", "ollama"):
                with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="fake-key"):
                    with patch("ai.genai.Client", return_value=client):
                        with patch("ai.requests.post", return_value=response) as post:
                            reply = ai.ask_ai("hello")
        self.assertEqual(reply, "Local fallback answer.")
        post.assert_called_once()

    def test_configured_key_is_rejected_before_a_provider_call(self):
        """Never transmit the API key even if it was pasted into a chat command."""
        with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="fake-key"):
            with patch("ai.genai.Client") as make_client:
                reply = ai.ask_ai("please use fake-key")
        self.assertIn("can't send a message", reply)
        make_client.assert_not_called()
        self.assertEqual(ai.CHAT_HISTORY, [])

    def test_failed_call_does_not_corrupt_chat_history(self):
        """Roll back the unfulfilled user message if the AI provider fails."""
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError("network disconnected")
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.config.AI_FALLBACK_PROVIDER", None):
                with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="fake-key"):
                    with patch("ai.genai.Client", return_value=client):
                        reply = ai.ask_ai("Failed question")
        self.assertIn("couldn't get an AI response", reply)
        self.assertEqual(ai.CHAT_HISTORY, [])

    def test_placeholder_key_in_env_returns_clear_message(self):
        """Detect when GEMINI_API_KEY is still the example template value."""
        with patch("ai.config.AI_PROVIDER", "gemini"):
            with patch("ai.load_dotenv"), patch("ai.os.getenv", return_value="your_key_here"):
                with patch("ai.genai.Client") as make_client:
                    reply = ai.ask_ai("hello")
        self.assertIn("GEMINI_API_KEY is missing", reply)
        make_client.assert_not_called()
        self.assertEqual(ai.CHAT_HISTORY, [])


if __name__ == "__main__":
    unittest.main()
