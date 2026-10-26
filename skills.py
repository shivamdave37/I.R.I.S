"""Small approved actions Iris can run after typed permission."""

from datetime import datetime
import json
import os
import shutil
import subprocess
import tempfile
import webbrowser

import ai
import config


def tell_time():
    """Return the local time in a readable format."""
    return datetime.now().astimezone().strftime("It is %I:%M %p.")


def tell_date():
    """Return today's local date in a readable format."""
    return datetime.now().astimezone().strftime("Today is %A, %B %d, %Y.")


def help_text():
    """List capabilities that are actually implemented in this starter build."""
    return (
        "I can open approved apps and websites, tell the time or date, save, show, search, and delete notes, "
        "and answer general questions through Gemini or Ollama. I can research with Gemini Search and draft "
        "inert skill proposals for review. I preview plans and ask before online research, opening, saving, "
        "deleting, or proposing code. Try: open Notepad, research Python 3.14 changes, note buy milk, "
        "search notes for milk, delete note 1, propose skill greeting for return a short greeting, or help."
    )


def open_approved(name):
    """Open only a configured app or website, with no shell command construction."""
    key = name.casefold().strip()
    if key in config.WEBSITES:
        if webbrowser.open(config.WEBSITES[key], new=2):
            return f"Opened {key}."
        return f"I couldn't open {key}. Check your default browser."
    app_path = config.APPS.get(key)
    if not app_path:
        return f"{key} is not on Iris's approved app or website list."
    resolved = shutil.which(app_path) or (app_path if os.path.isfile(app_path) else None)
    if not resolved:
        return f"I couldn't find {key}. Check its approved path in config.py."
    if hasattr(os, "startfile"):
        os.startfile(resolved)
    else:
        subprocess.Popen([resolved], shell=False)
    return f"Opened {key}."


def add_note(text):
    """Append one approved note to a JSON file inside Iris's data folder."""
    if not isinstance(text, str) or not text.strip():
        return "Add some note text first."
    path = config.DATA_FOLDER / "notes.json"
    if not _notes_path_is_safe(path):
        return "I refused to write because the notes path is redirected."
    notes = []
    if path.exists():
        try:
            notes = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
                return "The notes file has an unexpected format; nothing was changed."
        except (OSError, UnicodeError, json.JSONDecodeError):
            return "I couldn't read the notes file; nothing was changed."
    notes.append(text)
    try:
        config.DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(prefix="notes_", suffix=".tmp", dir=config.DATA_FOLDER)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as note_file:
                json.dump(notes, note_file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
    except OSError:
        return "I couldn't save the note."
    return "Note saved."


def _read_notes(path):
    """Load the existing note list without replacing damaged data."""
    if not path.exists():
        return []
    try:
        notes = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        return None
    return notes


def _write_notes(path, notes):
    """Replace the note file atomically after validating its project path."""
    try:
        config.DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(prefix="notes_", suffix=".tmp", dir=config.DATA_FOLDER)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as note_file:
                json.dump(notes, note_file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
    except OSError:
        return False
    return True


def _notes_path_is_safe(path):
    """Refuse note paths that resolve through a link outside the project."""
    try:
        project = config.PROJECT_FOLDER.resolve()
        data_folder = config.DATA_FOLDER.resolve()
        resolved_file = path.resolve()
        return (
            not config.DATA_FOLDER.is_symlink()
            and not path.is_symlink()
            and project in data_folder.parents
            and project in resolved_file.parents
        )
    except (OSError, RuntimeError):
        return False


def show_notes():
    """Read notes stored in the project's data folder."""
    path = config.DATA_FOLDER / "notes.json"
    if not _notes_path_is_safe(path):
        return "I refused to read because the notes path is redirected."
    notes = _read_notes(path)
    if notes is None:
        return "I couldn't read the notes file or it has an unexpected format."
    return "\n".join(f"{index}. {note}" for index, note in enumerate(notes, 1)) or "You don't have any notes yet."


def search_notes(query):
    """Find saved notes containing a case-insensitive keyword."""
    if not isinstance(query, str) or not query.strip():
        return "Type a keyword to search notes."
    path = config.DATA_FOLDER / "notes.json"
    if not _notes_path_is_safe(path):
        return "I refused to read because the notes path is redirected."
    notes = _read_notes(path)
    if notes is None:
        return "I couldn't read the notes file or it has an unexpected format."
    matches = [(index, note) for index, note in enumerate(notes, 1) if query.casefold() in note.casefold()]
    return "\n".join(f"{index}. {note}" for index, note in matches) or "No matching notes."


def delete_note(index, approved=False):
    """Delete one numbered note only after the caller has confirmed it."""
    if not approved:
        return "I need your typed confirmation before deleting a note."
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        return "Choose a valid positive note number."
    path = config.DATA_FOLDER / "notes.json"
    if not _notes_path_is_safe(path):
        return "I refused to write because the notes path is redirected."
    notes = _read_notes(path)
    if notes is None:
        return "I couldn't read the notes file or it has an unexpected format."
    if index > len(notes):
        return "That note number does not exist."
    removed = notes.pop(index - 1)
    if not _write_notes(path, notes):
        return "I couldn't delete the note."
    return f"Deleted note {index}: {removed}"


def research_web(query):
    """Run bounded Gemini Search and return its cited research report."""
    if not isinstance(query, str) or len(query.strip()) < 3 or len(query.strip()) > 500:
        return "Use a research query between 3 and 500 characters."
    return ai.research_web(query.strip())
