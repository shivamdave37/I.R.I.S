"""Small approved actions Iris can run after typed permission."""

from collections import deque
import ctypes
from datetime import datetime
import difflib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

import ai
import approval_context
import config
import device_profile


MAX_FILE_SEARCH_RESULTS = 30
MAX_FILE_SEARCH_QUERY_LENGTH = 120
MAX_FILE_SEARCH_DEPTH = 4
MAX_FILE_SEARCH_ENTRIES = 4000
_FILE_SEARCH_RESULTS = []


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
        "manage a to-do list (add task, show tasks, complete task, delete task), set timers and reminders, "
        "check system health (status, battery), check live weather, read or copy to clipboard, "
        "search filenames and folders in my configured Documents root, open a selected result after approval, "
        "and answer general questions through Gemini or Ollama. I can research with the configured web provider and draft "
        "inert skill proposals for review. I preview plans and ask before online research, opening, saving, "
        "deleting, or proposing code. Try: open Notepad, research Python 3.14 changes, add task study Python, "
        "tasks, set timer for 5 minutes, system status, battery, weather in London, note buy milk, "
        "search notes for milk, find file report.pdf, open result 1, delete note 1, "
        "capture screen, describe screen, click 120 220, type at 300,200: hello, "
        "propose skill greeting for return a short greeting, or help."
    )


def open_approved(name):
    """Open only a configured app or website, with no shell command construction."""
    key = name.casefold().strip()
    if key not in config.APPS and key not in config.WEBSITES:
        return f"{key} is not on Iris's approved app or website list."
    approval_context.require("open_target", {"target": key})
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
    approval_context.require("save_note", {"text": text})
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


def _write_notes(notes, deleted_index):
    """Write only the fixed note store for the currently approved deletion."""
    if isinstance(deleted_index, bool) or not isinstance(deleted_index, int) or deleted_index < 1:
        raise PermissionError("A valid approved note deletion is required.")
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        raise ValueError("Notes must be a list of text values.")
    approval_context.require("delete_note", {"index": deleted_index})
    path = config.DATA_FOLDER / "notes.json"
    if not _notes_path_is_safe(path):
        return False
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
    approval_context.require("delete_note", {"index": index})
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
    if not _write_notes(notes, index):
        return "I couldn't delete the note."
    return f"Deleted note {index}: {removed}"


def research_web(query):
    """Run bounded Gemini Search and return its cited research report."""
    if not isinstance(query, str) or len(query.strip()) < 3 or len(query.strip()) > 500:
        return "Use a research query between 3 and 500 characters."
    approval_context.require("research_web", {"query": query})
    return ai.research_web(query.strip())


def _is_link_or_junction(path):
    """Detect symlinks and Windows reparse points without following them."""
    try:
        details = path.lstat()
    except (OSError, RuntimeError):
        return None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(details, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _search_roots():
    """Resolve the explicitly configured roots before searching beneath them."""
    roots = []
    for configured_root in config.FILE_SEARCH_ROOTS:
        root = Path(configured_root).expanduser()
        # Do not bless the target of a configured-root junction or symlink.
        # Its destination must instead be configured as a root explicitly.
        if _is_link_or_junction(root) is not False:
            continue
        try:
            resolved = root.resolve(strict=False)
        except (OSError, RuntimeError):
            continue
        if resolved.is_dir() and resolved not in roots:
            roots.append(resolved)
    return roots


def _inside_root(path, roots):
    """Return whether a resolved path is contained by any approved root."""
    return any(path == root or path.is_relative_to(root) for root in roots)


def _name_similarity(query, target_name):
    """Compute similarity score between 0.0 and 1.0 using full ratio and token matching."""
    q = query.casefold().strip()
    t = target_name.casefold().strip()
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    full_ratio = difflib.SequenceMatcher(None, q, t).ratio()
    q_words = [w for w in re.split(r"[\s_.-]+", q) if len(w) > 1]
    t_words = [w for w in re.split(r"[\s_.-]+", t) if len(w) > 1]
    if q_words and t_words:
        token_scores = [max((difflib.SequenceMatcher(None, qw, tw).ratio() for tw in t_words), default=0.0) for qw in q_words]
        token_ratio = sum(token_scores) / len(token_scores)
    else:
        token_ratio = 0.0
    return max(full_ratio, token_ratio)


def search_files(query):
    """Search names only under configured roots with depth, work limits, and fuzzy fallback."""
    global _FILE_SEARCH_RESULTS
    _FILE_SEARCH_RESULTS = []
    if (not isinstance(query, str) or not query.strip() or len(query) > MAX_FILE_SEARCH_QUERY_LENGTH
            or query.strip() in {".", ".."} or "/" in query or "\\" in query
            or any(ord(character) < 32 for character in query)):
        return "Use a plain filename or folder-name query of 1 to 120 characters."
    roots = _search_roots()
    if not roots:
        return "File search is unavailable: no configured search root exists or is safe."

    needle = query.strip().casefold()
    folders = deque((root, 0) for root in roots)
    examined = 0
    partial = False
    limit_reached = False
    exact_matches = []
    fuzzy_candidates = []

    while folders and len(exact_matches) < MAX_FILE_SEARCH_RESULTS:
        folder, depth = folders.popleft()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    examined += 1
                    if examined > MAX_FILE_SEARCH_ENTRIES:
                        partial = True
                        limit_reached = True
                        folders.clear()
                        break
                    if entry.name.startswith("."):
                        continue
                    entry_path = Path(entry.path)
                    link_status = _is_link_or_junction(entry_path)
                    if link_status is None:
                        partial = True
                        continue
                    if link_status:
                        continue
                    try:
                        entry_details = entry.stat(follow_symlinks=False)
                        attributes = getattr(entry_details, "st_file_attributes", 0)
                        hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
                        if attributes & hidden_flag:
                            continue
                        is_directory = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError:
                        partial = True
                        continue
                    if not is_directory and not is_file:
                        continue
                    try:
                        resolved = entry_path.resolve(strict=False)
                    except (OSError, RuntimeError):
                        partial = True
                        continue
                    if not _inside_root(resolved, roots):
                        continue
                    kind = "folder" if is_directory else "file"
                    if needle in entry.name.casefold():
                        exact_matches.append((resolved, kind))
                        if len(exact_matches) >= MAX_FILE_SEARCH_RESULTS:
                            break
                    else:
                        score = _name_similarity(needle, entry.name)
                        if score >= 0.55:
                            fuzzy_candidates.append((score, resolved, kind))
                    if is_directory and depth < MAX_FILE_SEARCH_DEPTH:
                        folders.append((resolved, depth + 1))
        except OSError:
            partial = True
            continue

    is_fuzzy = False
    if exact_matches:
        _FILE_SEARCH_RESULTS = exact_matches
    elif fuzzy_candidates:
        fuzzy_candidates.sort(key=lambda item: item[0], reverse=True)
        seen = set()
        deduped = []
        for score, path, kind in fuzzy_candidates:
            if path not in seen:
                seen.add(path)
                deduped.append((path, kind))
                if len(deduped) >= MAX_FILE_SEARCH_RESULTS:
                    break
        _FILE_SEARCH_RESULTS = deduped
        is_fuzzy = True
    else:
        _FILE_SEARCH_RESULTS = []

    if not _FILE_SEARCH_RESULTS:
        if limit_reached:
            return "File search reached its safety limit; no matching results were found in the scanned portion."
        if partial:
            return "File search could not read some folders; no matching results were found in the readable portion."
        return "No matching files or folders were found in the configured search roots."

    if is_fuzzy:
        lines = [f"No exact match found. Nearest matching result(s):"]
    else:
        lines = [f"File search found {len(_FILE_SEARCH_RESULTS)} result(s):"]

    lines.extend(
        f"{index}. [{kind}] {path}"
        for index, (path, kind) in enumerate(_FILE_SEARCH_RESULTS, 1)
    )
    if limit_reached:
        lines.append("Search stopped at its configured work limit; these results may be incomplete.")
    elif partial:
        lines.append("Some folders could not be read; these results may be incomplete.")
    return "\n".join(lines)


def describe_search_result(index):
    """Return a still-valid selected path and type from the latest result list."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 1 or index > len(_FILE_SEARCH_RESULTS):
        return None
    cached_path, cached_kind = _FILE_SEARCH_RESULTS[index - 1]
    roots = _search_roots()
    if not roots or _is_link_or_junction(cached_path) is not False:
        return None
    try:
        resolved = cached_path.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if not _inside_root(resolved, roots):
        return None
    if resolved.is_dir():
        current_kind = "folder"
    elif resolved.is_file():
        current_kind = "file"
    else:
        return None
    if current_kind != cached_kind:
        return None
    return resolved, current_kind


def open_search_result(index):
    """Revalidate and open only a numbered result after gateway authorization."""
    selected = describe_search_result(index)
    if selected is None:
        return "That file-search result is no longer available or is outside the approved roots."
    path, kind = selected
    approval_context.require("open_search_result", {"index": index, "path": str(path)})
    if describe_search_result(index) != selected:
        return "The selected path changed after approval; nothing was opened. Search again."
    opener = getattr(os, "startfile", None)
    if opener is None:
        return "Opening selected files or folders is supported only on Windows."
    try:
        opener(str(path))
    except OSError:
        return f"I couldn't request Windows to open this {kind}: {path}"
    return (
        f"Windows launch requested for this {kind}: {path}. "
        "Iris cannot confirm that Windows opened it."
    )


# --- Task / To-Do Manager ---

def _tasks_path_is_safe(path):
    """Ensure tasks file stays within the configured data folder without symlink tricks."""
    try:
        resolved_folder = config.DATA_FOLDER.resolve()
        resolved_path = path.resolve()
        if not str(resolved_path).startswith(str(resolved_folder)):
            return False
        return not _is_link_or_junction(path)
    except (OSError, RuntimeError):
        return False


def _read_tasks(path):
    """Load existing tasks securely."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or not all(
        isinstance(t, dict) and "id" in t and "text" in t and "done" in t for t in data
    ):
        return None
    return data


def _write_tasks_file(tasks):
    """Safely write tasks file atomically."""
    path = config.DATA_FOLDER / "tasks.json"
    if not _tasks_path_is_safe(path):
        return False
    try:
        config.DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(prefix="tasks_", suffix=".tmp", dir=config.DATA_FOLDER)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
    except OSError:
        return False
    return True


def add_task(text):
    """Add a new task to the task list."""
    if not isinstance(text, str) or not text.strip():
        return "Add some task text first."
    approval_context.require("add_task", {"text": text})
    path = config.DATA_FOLDER / "tasks.json"
    tasks = _read_tasks(path)
    if tasks is None:
        return "The tasks file has an unexpected format; nothing was changed."
    next_id = max((t.get("id", 0) for t in tasks), default=0) + 1
    tasks.append({"id": next_id, "text": text.strip(), "done": False})
    if not _write_tasks_file(tasks):
        return "I couldn't save the task."
    return f"Task saved: {text.strip()} [ID: {next_id}]"


def list_tasks():
    """List all stored tasks."""
    path = config.DATA_FOLDER / "tasks.json"
    tasks = _read_tasks(path)
    if tasks is None:
        return "The tasks file has an unexpected format."
    if not tasks:
        return "No tasks saved yet. Add one with 'add task <text>'."
    lines = ["Tasks:"]
    for i, t in enumerate(tasks, 1):
        status = "[x]" if t.get("done") else "[ ]"
        lines.append(f"{i}. {status} {t.get('text', '')}")
    return "\n".join(lines)


def complete_task(index):
    """Mark a task as completed."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        return "A task number must be a positive integer."
    approval_context.require("complete_task", {"index": index})
    path = config.DATA_FOLDER / "tasks.json"
    tasks = _read_tasks(path)
    if tasks is None:
        return "The tasks file has an unexpected format; nothing was changed."
    if index > len(tasks):
        return f"Task {index} does not exist. Use 'show tasks' to see active tasks."
    target = tasks[index - 1]
    target["done"] = True
    if not _write_tasks_file(tasks):
        return "I couldn't update the task."
    return f"Marked task {index} as completed: '{target['text']}'"


def delete_task(index):
    """Delete a task from the list."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        return "A task number must be a positive integer."
    approval_context.require("delete_task", {"index": index})
    path = config.DATA_FOLDER / "tasks.json"
    tasks = _read_tasks(path)
    if tasks is None:
        return "The tasks file has an unexpected format; nothing was changed."
    if index > len(tasks):
        return f"Task {index} does not exist. Use 'show tasks' to see active tasks."
    removed = tasks.pop(index - 1)
    if not _write_tasks_file(tasks):
        return "I couldn't delete the task."
    return f"Deleted task {index}: '{removed['text']}'"


# --- Timers & Reminders ---

_ACTIVE_TIMERS = []
_TIMER_LOCK = threading.Lock()


def _fire_timer(timer_id, message):
    with _TIMER_LOCK:
        _ACTIVE_TIMERS[:] = [t for t in _ACTIVE_TIMERS if t["id"] != timer_id]
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass
    print(f"\n\n🔔 [Iris Reminder]: {message}\n", flush=True)


def set_timer(seconds, message):
    """Set an in-process background timer that alerts when finished."""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 1:
        return "Timer seconds must be a positive integer."
    if not isinstance(message, str) or not message.strip():
        message = "Timer finished!"
    approval_context.require("set_timer", {"seconds": seconds, "message": message})
    timer_id = int(time.time() * 1000)
    timer_obj = threading.Timer(seconds, _fire_timer, args=[timer_id, message])
    timer_obj.daemon = True
    with _TIMER_LOCK:
        _ACTIVE_TIMERS.append({
            "id": timer_id,
            "seconds": seconds,
            "message": message,
            "target_time": time.time() + seconds,
            "thread": timer_obj,
        })
    timer_obj.start()
    if seconds >= 60:
        mins = seconds // 60
        secs = seconds % 60
        time_desc = f"{mins} minute(s)" if secs == 0 else f"{mins}m {secs}s"
    else:
        time_desc = f"{seconds} second(s)"
    return f"Timer set for {time_desc}: '{message}'."


def list_timers():
    """List currently active timers."""
    now = time.time()
    with _TIMER_LOCK:
        active = [t for t in _ACTIVE_TIMERS if t["target_time"] > now]
    if not active:
        return "No active timers running."
    lines = ["Active timers:"]
    for i, t in enumerate(active, 1):
        rem = max(0, int(t["target_time"] - now))
        lines.append(f"{i}. '{t['message']}' - {rem}s remaining")
    return "\n".join(lines)


# --- System Status & Battery ---

def system_status():
    """Report safe, read-only system hardware metrics."""
    parts = []
    dev = device_profile.CURRENT_DEVICE
    parts.append(f"Model: {dev.system_model}")
    parts.append(f"OS: {dev.os_full} ({dev.architecture})")
    cpu_count = os.cpu_count() or 1
    parts.append(f"CPU: {dev.processor} ({cpu_count} logical cores)")
    parts.append(f"GPU: {dev.gpu}")
    try:
        class _MEM(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('sullAvailExtendedVirtual', ctypes.c_ulonglong)
            ]
        m = _MEM()
        m.dwLength = ctypes.sizeof(_MEM)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            total_gb = m.ullTotalPhys / (1024 ** 3)
            avail_gb = m.ullAvailPhys / (1024 ** 3)
            used_gb = total_gb - avail_gb
            parts.append(f"RAM: {m.dwMemoryLoad}% used ({used_gb:.1f} GB / {total_gb:.1f} GB)")
    except Exception:
        pass
    try:
        sys_drive = os.environ.get("SystemDrive", "C:") + "\\"
        disk = shutil.disk_usage(sys_drive)
        total_disk = disk.total / (1024 ** 3)
        free_disk = disk.free / (1024 ** 3)
        used_disk = disk.used / (1024 ** 3)
        percent = (disk.used / disk.total) * 100
        parts.append(f"Disk ({sys_drive}): {percent:.1f}% used ({used_disk:.1f} GB / {total_disk:.1f} GB, {free_disk:.1f} GB free)")
    except Exception:
        pass
    return "System Status:\n" + "\n".join(f"- {p}" for p in parts)


def battery_status():
    """Report battery percentage and charging state."""
    try:
        class _SPS(ctypes.Structure):
            _fields_ = [
                ('ACLineStatus', ctypes.c_byte),
                ('BatteryFlag', ctypes.c_byte),
                ('BatteryLifePercent', ctypes.c_byte),
                ('Reserved1', ctypes.c_byte),
                ('BatteryLifeTime', ctypes.c_ulong),
                ('BatteryFullLifeTime', ctypes.c_ulong)
            ]
        s = _SPS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            percent = int(s.BatteryLifePercent)
            if percent == 255:
                return "No battery detected (desktop PC or power supply)."
            ac = "Plugged in (charging)" if s.ACLineStatus == 1 else "On battery (unplugged)"
            return f"Battery: {percent}% - {ac}"
    except Exception:
        pass
    return "Battery information is unavailable."


# --- Live Weather ---

def get_weather(location):
    """Fetch brief live weather using wttr.in without requiring external API keys."""
    clean_loc = str(location or "").strip()
    encoded = urllib.parse.quote(clean_loc) if clean_loc else ""
    url = f"https://wttr.in/{encoded}?format=3" if encoded else "https://wttr.in/?format=3"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode("utf-8").strip()
            if content and not content.startswith("<"):
                return f"Weather: {content}"
            return f"Could not retrieve weather for {clean_loc}."
    except Exception:
        return f"Weather service is currently unreachable for {clean_loc or 'your location'}."


# --- Clipboard ---

def read_clipboard():
    """Read text from the clipboard."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            content = root.clipboard_get()
        finally:
            root.destroy()
        if not content:
            return "Clipboard is empty."
        preview = content[:200] + ("..." if len(content) > 200 else "")
        return f"Clipboard content ({len(content)} chars):\n{preview}"
    except Exception:
        return "Clipboard is empty or does not contain text."


def copy_to_clipboard(text):
    """Copy approved text to the clipboard."""
    if not isinstance(text, str) or not text.strip():
        return "Add some text to copy."
    approval_context.require("copy_to_clipboard", {"text": text})
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
        finally:
            root.destroy()
        return f"Copied {len(text)} characters to clipboard."
    except Exception:
        return "Failed to copy text to clipboard."
