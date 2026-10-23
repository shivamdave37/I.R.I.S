"""Match typed commands to the small set of Stage 1 skills."""

import re

import config
from skills import apps, timeinfo, web


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
    """Give a simple reply until the AI chat stage is built."""
    # Unknown commands fall through here until AI chat is added in Stage 3.
    return "I don't know that yet."


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

    # Any other command, including punctuation-only input, goes to the fallback.
    return fallback(command)

