"""Save and read personal notes in the project data folder."""

import os
import threading

import config


_notes_lock = threading.Lock()


def add_note(note_text):
    """Append one note to the local notes file."""
    if not isinstance(note_text, str) or not note_text.strip():
        return "Please include text for the note."
    try:
        os.makedirs(config.DATA_FOLDER, exist_ok=True)
        notes_path = os.path.join(config.DATA_FOLDER, "notes.txt")
        # One lock prevents two tasks from interleaving writes to the notes file.
        with _notes_lock:
            with open(notes_path, "a", encoding="utf-8") as notes_file:
                notes_file.write(note_text.strip() + "\n")
        return "I saved your note."
    except OSError:
        return "I couldn't save that note. Please check the project data folder."


def show_notes():
    """Return saved notes or explain that there are none yet."""
    notes_path = os.path.join(config.DATA_FOLDER, "notes.txt")
    try:
        # The same lock protects reads while a note is being appended.
        with _notes_lock:
            with open(notes_path, "r", encoding="utf-8") as notes_file:
                notes = notes_file.read().strip()
        return notes or "You don't have any notes yet."
    except FileNotFoundError:
        return "You don't have any notes yet."
    except OSError:
        return "I couldn't read your notes. Please check the project data folder."
