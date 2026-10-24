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
IRIS_RESOURCES = ["MIC_SPEAKER", "CLIPBOARD", "SCREEN_FOCUS", "GIT_REPO", "API_QUOTA", "NOTES_FILE"]
ALLOWED_SKILLS = ["open", "timeinfo", "news", "code_helper", "github_tools", "notes", "memory", "chat"]
RESOURCE_REASONS = {
    ("CLIPBOARD", "code_helper"): "to read the code you selected",
    ("SCREEN_FOCUS", "code_helper"): "to copy from your active window",
    ("SCREEN_FOCUS", "open"): "to open the approved app or website",
    ("API_QUOTA", "code_helper"): "to send selected code to the AI",
    ("API_QUOTA", "news"): "to fetch current headlines",
    ("API_QUOTA", "chat"): "to ask the configured AI provider",
    ("MIC_SPEAKER", "chat"): "to use voice input/output when enabled",
    ("MIC_SPEAKER", "news"): "to speak the news when enabled",
    ("GIT_REPO", "github_tools"): "to inspect or change this Git repository",
    ("NOTES_FILE", "notes"): "to read or write your notes",
}

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
