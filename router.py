"""Match commands to the configured skills and AI fallback."""

import re

import config
from ai import ask_ai
from skills import apps, news, timeinfo, web


def normalize(command):
    """Lowercase input, remove punctuation, and collapse extra spaces."""
    # Guard against None and non-string inputs so we never crash on empty input.
    if not command:
        return ""
    # Strip punctuation and collapse internal whitespace to single spaces.
    cleaned = re.sub(r"[^\w\s]", "", command.lower())
    return " ".join(cleaned.split())


def is_exit_command(command):
    """Recognize only the explicit Stage 1 exit words."""
    # Compare against fixed exit keywords after normalization.
    return normalize(command) in {"exit", "quit"}


def fallback(command):
    """Send unknown commands to the single configured AI chat function."""
    # Keep provider details inside ai.py so routing stays independent of the AI service.
    return ask_ai([{"role": "user", "content": command}])


def handle(command):
    """Route a command to an approved Stage 1 skill or the fallback."""
    # Truly empty input returns empty string to avoid accidental fallback replies.
    if not command or not str(command).strip():
        return ""

    normalized = normalize(command)
    # Check for exit commands first so the loop knows when to stop.
    if normalized in {"exit", "quit"}:
        return "Goodbye!"

    # Handle website and app opening commands starting with 'open '.
    if normalized.startswith("open "):
        name = normalized[5:].strip()
        if name in config.WEBSITES:
            return web.open_website(name)
        if name in config.APPS:
            return apps.open_app(name)
        return f"I can't open {name}; it is not on the approved list."

    # Direct time queries.
    if normalized in {"time", "what is the time", "whats the time", "tell me the time"}:
        return timeinfo.tell_time()
    # Direct date queries.
    if normalized in {"date", "what is the date", "whats the date", "tell me the date"}:
        return timeinfo.tell_date()
    # Direct news queries.
    if normalized in {"news", "latest news", "whats the news", "what is the news", "tell me the news"}:
        return news.get_news()

    # Any other command, including punctuation-only input, goes to the fallback.
    return fallback(command)

