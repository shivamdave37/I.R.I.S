"""Match commands to the configured skills and AI fallback."""

import re

import config
from ai import ask_ai
from skills import apps, code_helper, github_tools, memory, news, notes, timeinfo, web


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

    if normalized.startswith("explain this code"):
        return code_helper.explain_code()
    if normalized.startswith("fix this code"):
        return code_helper.suggest_fix()
    if normalized == "save my work to github":
        return github_tools.save_to_github()
    if normalized.startswith("take a note"):
        # Keep the user's original note text instead of its normalized command form.
        note_text = str(command).strip()[len("take a note"):].strip()
        return notes.add_note(note_text)
    if normalized == "show my notes":
        return notes.show_notes()
    if normalized.startswith("my name is "):
        name = str(command).strip()[len("my name is"):].strip()
        return memory.remember_name(name)
    if normalized in {"my name", "what is my name", "what do you remember about me"}:
        return memory.get_memory()
    if normalized.startswith("remember i prefer "):
        preference = str(command).strip()[len("remember i prefer"):].strip()
        return memory.remember_preference(preference)

    # Any other command, including punctuation-only input, goes to the fallback.
    return fallback(command)

