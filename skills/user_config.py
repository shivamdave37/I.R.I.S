"""Save user-approved app and website entries under the project data folder."""

import difflib
import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

import config
from iris.console import request_input


_CONFIG_LOCK = threading.Lock()
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 ]{1,30}$")
_WARNED_LOAD_STATE = None


def _empty_config():
    """Return the empty user configuration shape."""
    return {"apps": {}, "websites": {}}


def _config_path():
    """Resolve the user config path and refuse paths outside project data."""
    project_path = Path(config.PROJECT_FOLDER).resolve()  # PROTECTED
    data_candidate = Path(config.DATA_FOLDER)
    expected_data_path = project_path / "data"
    if data_candidate.is_symlink() or data_candidate.resolve() != expected_data_path:  # PROTECTED
        raise ValueError("The user config must stay in the project's data folder.")
    data_path = expected_data_path
    config_path = data_path / "user_config.json"
    if config_path.is_symlink():  # PROTECTED
        raise ValueError("The user config file cannot be a symbolic link.")
    return config_path


def _warn_once(state, message):
    """Log a configuration problem once until the file becomes readable."""
    global _WARNED_LOAD_STATE
    if state != _WARNED_LOAD_STATE:
        logging.warning("User app and website settings %s; starting with an empty list.", message)
        _WARNED_LOAD_STATE = state


def _read_locked():
    """Read and validate saved entries while the config lock is held."""
    global _WARNED_LOAD_STATE
    try:
        path = _config_path()
        with path.open("r", encoding="utf-8") as user_file:
            saved = json.load(user_file)
        if not isinstance(saved, dict):
            raise ValueError("the file must contain a JSON object")
        cleaned = _empty_config()
        for kind, builtins in (("apps", config.APPS), ("websites", config.WEBSITES)):
            values = saved.get(kind, {})
            if not isinstance(values, dict):
                raise ValueError(f"{kind} must be an object")
            for name, value in values.items():
                normalized = _validate_name(name)
                if not normalized or normalized in builtins or not isinstance(value, str) or not value.strip():
                    continue
                if kind == "apps" and os.path.splitext(value)[1].lower() in {".exe", ".lnk"}:
                    cleaned[kind][normalized] = value.strip()
                elif kind == "websites" and _validate_website_url(value):
                    cleaned[kind][normalized] = value.strip()
        _WARNED_LOAD_STATE = None
        return cleaned
    except FileNotFoundError:
        _warn_once("missing", "are missing")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _warn_once("invalid", f"could not be read ({type(error).__name__})")
    return _empty_config()


def load_user_config():
    """Load the saved user app and website entries safely."""
    with _CONFIG_LOCK:
        return _read_locked()


def initialize():
    """Check local settings during startup so damaged files are reported early."""
    load_user_config()


def learned_apps():
    """Return a copy of the learned app entries."""
    return load_user_config()["apps"]


def learned_websites():
    """Return a copy of the learned website entries."""
    return load_user_config()["websites"]


def _validate_name(name):
    """Normalize a permitted name or return an empty string when invalid."""
    if not isinstance(name, str):
        return ""
    cleaned = " ".join(name.split())
    if not _NAME_PATTERN.fullmatch(cleaned):
        return ""
    return cleaned.lower()


def _validate_website_url(url):
    """Return an HTTPS URL with a valid hostname, or an empty string."""
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        # A supplied HTTP scheme is refused instead of silently changing the destination.
        if parsed.scheme.lower() != "https" or not hostname or parsed.username or parsed.password:
            return ""
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return ""
        ascii_host = hostname.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""
    labels = ascii_host.rstrip(".").split(".")
    if not ascii_host or len(ascii_host) > 253 or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels):
        return ""
    return candidate


def _start_menu_folders():
    """Return the all-users and current-user Start Menu program folders."""
    folders = []
    for variable in ("PROGRAMDATA", "APPDATA"):
        base = os.environ.get(variable)
        if base:
            folders.append(os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs"))
    return folders


def _find_shortcut(name):
    """Find the closest named Start Menu shortcut without launching it."""
    wanted = _validate_name(name)
    matches = []
    for folder in _start_menu_folders():
        if not os.path.isdir(folder):
            continue
        for current, _, filenames in os.walk(folder):
            for filename in filenames:
                if filename.lower().endswith(".lnk"):
                    stem = os.path.splitext(filename)[0].lower()
                    ratio = difflib.SequenceMatcher(None, wanted, stem).ratio()
                    if stem == wanted:
                        score = 3.0
                    elif stem.startswith(wanted):
                        score = 2.0 + ratio
                    elif wanted in stem:
                        score = 1.0 + ratio
                    else:
                        score = ratio
                    matches.append((score, os.path.join(current, filename)))
    if not matches:
        return ""
    score, path = max(matches, key=lambda item: item[0])
    return path if score >= 0.6 else ""


def _typed_yes(question):
    """Accept approval only when the keyboard response is exactly yes."""
    answer = request_input(question + " Type yes to continue, or no to cancel: ")
    return isinstance(answer, str) and answer.strip().lower() == "yes"


def _save_locked(settings):
    """Write settings atomically while the config lock is held."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Resolve again after creating the folder so a redirected data folder is refused.
    path = _config_path()
    temporary_path = None
    try:
        file_descriptor, temporary_path = tempfile.mkstemp(prefix="user_config_", suffix=".tmp", dir=path.parent)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as user_file:
            json.dump(settings, user_file, indent=2, ensure_ascii=False)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def _add_item(kind, name, value):
    """Save one confirmed user entry without replacing a built-in name."""
    builtins = config.APPS if kind == "apps" else config.WEBSITES
    normalized = _validate_name(name)
    if not normalized:
        return "Names can use only letters, numbers, and spaces (1 to 30 characters)."
    if normalized in builtins:
        return f"{normalized} is built in and cannot be replaced."
    settings = load_user_config()
    if normalized in settings[kind]:
        return f"{normalized} is already in your learned {kind}. Remove it first if you want to replace it."
    print(f"Add {kind[:-1]} {normalized}: {value}")
    if not _typed_yes("Save this entry?"):
        return "Cancelled; nothing was saved."
    with _CONFIG_LOCK:
        settings = _read_locked()
        if normalized in settings[kind] or normalized in builtins:
            return f"{normalized} already exists; nothing was saved."
        settings[kind][normalized] = value
        try:
            _save_locked(settings)
        except (OSError, ValueError) as error:
            logging.error("Could not save learned %s: %s", kind, type(error).__name__)
            return "I couldn't save that entry. Check the project data folder."
    return f"Added {kind[:-1]} {normalized}."


def add_app(name):
    """Find an approved app shortcut or ask for a valid executable path."""
    normalized = _validate_name(name)
    if not normalized:
        return "Names can use only letters, numbers, and spaces (1 to 30 characters)."
    if normalized in config.APPS:
        return f"{normalized} is built in and cannot be replaced."
    shortcut = _find_shortcut(normalized)
    if shortcut:
        app_path = shortcut
        print(f"Start Menu match for {normalized}: {app_path}")
    else:
        app_path = request_input(f"No Start Menu shortcut found for {normalized}. Type its full .exe or .lnk path: ")
        if not isinstance(app_path, str):
            return "No path was provided; nothing was saved."
        app_path = app_path.strip().strip('"')
    if os.path.splitext(app_path)[1].lower() not in {".exe", ".lnk"} or not os.path.isfile(app_path):
        return "That path must exist and end in .exe or .lnk. Nothing was saved."
    return _add_item("apps", normalized, app_path)


def add_website(name, url):
    """Validate and ask before saving one HTTPS website."""
    normalized = _validate_name(name)
    if not normalized:
        return "Names can use only letters, numbers, and spaces (1 to 30 characters)."
    website_url = _validate_website_url(url)
    if not website_url:
        return "Use an HTTPS URL with a valid hostname. Nothing was saved."
    return _add_item("websites", normalized, website_url)


def remove_item(kind, name):
    """Remove one learned app or website only after typed confirmation."""
    normalized = _validate_name(name)
    if not normalized:
        return "Names can use only letters, numbers, and spaces (1 to 30 characters)."
    settings = load_user_config()
    if normalized not in settings[kind]:
        return f"{normalized} is not in your learned {kind}."
    value = settings[kind][normalized]
    print(f"Remove {kind[:-1]} {normalized}: {value}")
    if not _typed_yes("Remove this entry?"):
        return "Cancelled; nothing was removed."
    with _CONFIG_LOCK:
        settings = _read_locked()
        if normalized not in settings[kind]:
            return f"{normalized} is no longer in your learned {kind}."
        del settings[kind][normalized]
        try:
            _save_locked(settings)
        except (OSError, ValueError) as error:
            logging.error("Could not remove learned %s: %s", kind, type(error).__name__)
            return "I couldn't update the project data folder."
    return f"Removed {kind[:-1]} {normalized}."


def handle(command):
    """Handle fixed commands for adding, removing, and listing user entries."""
    text = command.strip()
    match = re.fullmatch(r"add\s+app\s+(.+)", text, re.IGNORECASE)
    if match:
        return add_app(match.group(1))
    match = re.fullmatch(r"add\s+website\s+(.+?)\s+(\S+)", text, re.IGNORECASE)
    if match:
        return add_website(match.group(1), match.group(2))
    match = re.fullmatch(r"remove\s+app\s+(.+)", text, re.IGNORECASE)
    if match:
        return remove_item("apps", match.group(1))
    match = re.fullmatch(r"remove\s+website\s+(.+)", text, re.IGNORECASE)
    if match:
        return remove_item("websites", match.group(1))
    if text.lower() == "list apps":
        items = available_apps_with_source()
        return "Apps: " + ("; ".join(f"{name} ({source})" for name, source in items) or "none")
    if text.lower() == "list websites":
        items = available_websites_with_source()
        return "Websites: " + ("; ".join(f"{name} ({url})" for name, url in items) or "none")
    return "I couldn't understand that app or website command."


def available_apps_with_source():
    """Return built-in and learned app names with their configured paths."""
    return sorted({**learned_apps(), **config.APPS}.items())


def available_websites_with_source():
    """Return built-in and learned website names with their configured URLs."""
    return sorted({**learned_websites(), **config.WEBSITES}.items())
