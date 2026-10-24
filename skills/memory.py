"""Remember the user's name, preferences, and recent commands."""

import json
import os
import threading

import config
from dotenv import load_dotenv


_memory_lock = threading.Lock()


def _empty_memory():
    """Return the default memory shape used when no valid file exists."""
    # A consistent set of keys keeps each memory command simple to read.
    return {"name": "", "preferences": [], "history": []}


def _read_memory():
    """Read memory safely and return an empty structure for a missing or damaged file."""
    memory_path = os.path.join(config.DATA_FOLDER, "memory.json")
    try:
        with open(memory_path, "r", encoding="utf-8") as memory_file:
            memory = json.load(memory_file)
        if not isinstance(memory, dict):
            raise ValueError("Memory must be an object")
        defaults = _empty_memory()
        for key, value in defaults.items():
            if not isinstance(memory.get(key), type(value)):
                memory[key] = value
        return memory
    except (OSError, ValueError, json.JSONDecodeError):
        # A corrupt memory file must not stop the assistant from starting.
        return _empty_memory()


def _write_memory(memory):
    """Write memory as readable JSON while holding its shared-file lock."""
    # Callers hold the lock so simultaneous updates cannot overwrite one another.
    os.makedirs(config.DATA_FOLDER, exist_ok=True)
    memory_path = os.path.join(config.DATA_FOLDER, "memory.json")
    with open(memory_path, "w", encoding="utf-8") as memory_file:
        json.dump(memory, memory_file, indent=2, ensure_ascii=False)


def remember_name(name):
    """Save the user's name in the local memory file."""
    # Keep only the latest supplied name so answers stay unambiguous.
    name = name.strip()
    if not name:
        return "Please tell me the name to remember."
    try:
        with _memory_lock:
            memory = _read_memory()
            memory["name"] = name
            _write_memory(memory)
        return f"I'll remember your name is {name}."
    except OSError:
        return "I couldn't save that memory. Please check the project data folder."


def remember_preference(preference):
    """Add a preference to the local memory file without duplicates."""
    # Deduplication avoids repeating the same preference in future replies.
    preference = preference.strip()
    if not preference:
        return "Please include a preference to remember."
    try:
        with _memory_lock:
            memory = _read_memory()
            if preference not in memory["preferences"]:
                memory["preferences"].append(preference)
            _write_memory(memory)
        return "I'll remember that preference."
    except OSError:
        return "I couldn't save that memory. Please check the project data folder."


def get_memory():
    """Return remembered name and preferences in a short message."""
    # Read under the lock so a simultaneous save cannot produce a partial view.
    with _memory_lock:
        memory = _read_memory()
    parts = []
    if memory["name"]:
        parts.append(f"Your name is {memory['name']}.")
    if memory["preferences"]:
        parts.append("Your preferences: " + "; ".join(memory["preferences"]) + ".")
    return " ".join(parts) if parts else "I haven't saved your name or preferences yet."


def record_command(command):
    """Keep only the latest twenty commands in local memory."""
    try:
        # The history is persistent, so redact the configured key like the log does.
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        safe_command = str(command).replace(api_key, "[REDACTED]") if api_key else str(command)
        with _memory_lock:
            memory = _read_memory()
            memory["history"].append(safe_command)
            memory["history"] = memory["history"][-20:]
            _write_memory(memory)
    except OSError:
        # Command history is helpful but must never break the command loop.
        pass
