"""Safe, beginner-readable settings for Iris."""

from pathlib import Path


PROJECT_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = PROJECT_FOLDER / "data"
LOG_FOLDER = PROJECT_FOLDER / "logs"

AI_PROVIDER = "gemini"
GEMINI_MODEL = "gemini-3.5-flash-lite"
OLLAMA_MODEL = "gemma3:1b"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

# Iris can only open entries listed here. Add personal apps after checking their paths.
APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
}
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
}

# File search roots: checks Documents, Desktop, Downloads, and active OneDrive folders.
def _default_search_roots():
    candidates = [
        Path.home() / "Documents",
        Path.home() / "OneDrive" / "Documents",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
    ]
    roots = []
    for candidate in candidates:
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots or [Path.home() / "Documents"]

FILE_SEARCH_ROOTS = _default_search_roots()

# UI Automation starts in a tiny local-app allowlist. Browser and unknown
# processes remain unsupported so webpage content cannot become UI commands.
UI_ALLOWED_PROCESS_NAMES = frozenset({"notepad.exe", "calculator.exe", "calculatorapp.exe"})
