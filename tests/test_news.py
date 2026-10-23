"""Tests for the RSS news skill without live internet access."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import router
from skills import news


class NewsTests(unittest.TestCase):
    """Check headline formatting and graceful feed failures."""

    def test_news_returns_five_headlines(self):
        """Format the first five feed entries into a spoken-friendly reply."""
        response = Mock(content=b"<rss/>")
        entries = [{"title": f"Headline {number}"} for number in range(1, 7)]
        with patch("skills.news.requests.get", return_value=response) as get_feed:
            with patch("skills.news.feedparser.parse", return_value=SimpleNamespace(entries=entries)):
                reply = news.get_news()
        get_feed.assert_called_once_with(news.config.NEWS_RSS_URL, timeout=10)
        for number in range(1, 6):
            self.assertIn(f"Headline {number}", reply)
        self.assertNotIn("Headline 6", reply)

    def test_failed_feed_returns_clear_message(self):
        """Return a friendly message when the RSS request fails."""
        with patch("skills.news.requests.get", side_effect=RuntimeError("offline")):
            reply = news.get_news()
        self.assertIn("couldn't fetch the latest news", reply)

    def test_news_command_uses_news_skill_without_ai(self):
        """Route news phrases directly to the news skill."""
        with patch("router.news.get_news", return_value="Headline reply") as get_news:
            with patch("router.ask_ai") as ask_ai:
                self.assertEqual(router.handle("LATEST NEWS!"), "Headline reply")
        get_news.assert_called_once_with()
        ask_ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
