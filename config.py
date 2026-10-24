"""Settings for the Mini Jarvis project."""

import os

MODE = "both"
AI_PROVIDER = "gemini"
AI_FALLBACK_PROVIDER = None
USE_IRIS = False
GEMINI_MODEL = "gemini-3.5-flash-lite"
OLLAMA_MODEL = "gemma3:1b"
OLLAMA_URL = "http://localhost:11434/api/chat"
NEWS_RSS_URL = "https://feeds.bbci.co.uk/news/rss.xml"
PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")

WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
}

# Replace YOUR_USERNAME with the Windows account name and confirm each app path.
APPS = {
    "vscode": r"C:\Users\YOUR_USERNAME\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "notepad": "notepad.exe",
    "codex": r"C:\Users\YOUR_USERNAME\AppData\Local\Programs\Codex\Codex.exe",
}
