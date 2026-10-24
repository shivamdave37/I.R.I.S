"""Fetch and format a few headlines from the configured RSS feed."""

import html
import feedparser
import requests

import config


def get_news():
    """Return up to five headlines or a clear message when the feed fails."""
    try:
        # Fetch RSS feed with a timeout so a slow connection does not freeze Jarvis.
        response = requests.get(config.NEWS_RSS_URL, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        # Clean HTML entities from titles so spoken and printed headlines read naturally.
        headlines = [
            html.unescape(entry.get("title", "")).strip()
            for entry in feed.entries
            if entry.get("title", "").strip()
        ]
        if not headlines:
            return "I couldn't find any headlines in the news feed right now."
        # Limit to the top 5 headlines as specified.
        top_headlines = headlines[:5]
        numbered_headlines = [f"{number}. {title}" for number, title in enumerate(top_headlines, start=1)]
        return "Here are the latest headlines: " + " ".join(numbered_headlines)
    except Exception:
        # A network or feed parsing problem should leave Jarvis ready for the next command.
        return "I couldn't fetch the latest news right now. Please check your internet connection."

