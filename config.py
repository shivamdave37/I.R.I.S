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
