"""Match typed commands to the small set of Stage 1 skills."""

import re

import config
from skills import apps, timeinfo, web


def normalize(command):
    """Lowercase input and remove punctuation for predictable matching."""
    return re.sub(r"[^\w\s]", "", command.lower()).strip()


def is_exit_command(command):
    """Recognize only the explicit Stage 1 exit words."""
    return normalize(command) in {"exit", "quit"}


def fallback(command):
    """Give a simple reply until the AI chat stage is built."""
    return "I don't know that yet."


def handle(command):
    """Route a command to an approved Stage 1 skill or the fallback."""
    normalized = normalize(command)
    if not normalized:
        return ""
    if normalized in {"exit", "quit"}:
        return "Goodbye!"

    if normalized.startswith("open "):
        name = normalized[5:].strip()
        if name in config.WEBSITES:
            return web.open_website(name)
        if name in config.APPS:
            return apps.open_app(name)
        return f"I can't open {name}; it is not on the approved list."

    if normalized in {"time", "what is the time", "whats the time", "tell me the time"}:
        return timeinfo.tell_time()
    if normalized in {"date", "what is the date", "whats the date", "tell me the date"}:
        return timeinfo.tell_date()
    return fallback(command)
