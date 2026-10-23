"""Fetch and format a few headlines from the configured RSS feed."""

import feedparser
import requests

import config


def get_news():
    """Return up to five headlines or a clear message when the feed fails."""
    try:
        response = requests.get(config.NEWS_RSS_URL, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        headlines = [entry.get("title", "").strip() for entry in feed.entries if entry.get("title", "").strip()]
        if not headlines:
            return "I couldn't find any headlines in the news feed right now."
        top_headlines = headlines[:5]
        numbered_headlines = [f"{number}. {title}" for number, title in enumerate(top_headlines, start=1)]
        return "Here are the latest headlines: " + " ".join(numbered_headlines)
    except Exception:
        # A network or feed parsing problem should leave Jarvis ready for the next command.
        return "I couldn't fetch the latest news right now. Please check your internet connection."
