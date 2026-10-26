"""Settings for the Mini Jarvis project."""

import os

MODE = "typed"
AI_PROVIDER = "gemini"
AI_FALLBACK_PROVIDER = None
USE_IRIS = True
GEMINI_MODEL = "gemini-3.5-flash-lite"
OLLAMA_MODEL = "gemma3:1b"
OLLAMA_URL = "http://localhost:11434/api/chat"
NEWS_RSS_URL = "https://feeds.bbci.co.uk/news/rss.xml"
PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")
WAKE_ENABLED = False
WAKE_WORD = "iris"
WAKE_MODEL_PATH = os.path.join(PROJECT_FOLDER, "models", "vosk-model-small-en-in-0.4")
WAKE_CHUNK_TIMEOUT = 1
WAKE_PHRASE_LIMIT = 3
WAKE_COMMAND_TIMEOUT = 5
WAKE_COMMAND_LIMIT = 8
IRIS_RESOURCES = ["MIC_SPEAKER", "CLIPBOARD", "SCREEN_FOCUS", "GIT_REPO", "API_QUOTA", "NOTES_FILE", "USER_CONFIG_FILE", "LEARNED_SKILLS"]
ALLOWED_SKILLS = ["open", "timeinfo", "news", "code_helper", "github_tools", "notes", "memory", "chat", "user_config", "learned_skills"]
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
    ("NOTES_FILE", "memory"): "to save or read your saved name and preferences",
    ("API_QUOTA", "open"): "to allow the open skill to use the configured AI service if needed",
    ("API_QUOTA", "timeinfo"): "to allow the time skill to use the configured AI service if needed",
    ("API_QUOTA", "news"): "to fetch current headlines",
    ("API_QUOTA", "code_helper"): "to send selected code to the AI",
    ("API_QUOTA", "github_tools"): "to allow the Git helper to use the configured AI service if needed",
    ("API_QUOTA", "notes"): "to allow the notes skill to use the configured AI service if needed",
    ("API_QUOTA", "memory"): "to allow the memory skill to use the configured AI service if needed",
    ("API_QUOTA", "chat"): "to ask the configured AI provider",
    ("MIC_SPEAKER", "open"): "to hear your command and speak the reply",
    ("MIC_SPEAKER", "timeinfo"): "to hear your command and speak the reply",
    ("MIC_SPEAKER", "news"): "to hear your command and speak the headlines",
    ("MIC_SPEAKER", "code_helper"): "to hear your command and speak the code summary",
    ("MIC_SPEAKER", "github_tools"): "to hear your command and speak the result",
    ("MIC_SPEAKER", "notes"): "to hear your command and speak the notes result",
    ("MIC_SPEAKER", "memory"): "to hear your command and speak the memory result",
    ("MIC_SPEAKER", "chat"): "to hear your command and speak the AI reply",
    ("USER_CONFIG_FILE", "user_config"): "to save your approved app and website list",
    ("API_QUOTA", "learned_skills"): "to ask AI for the skill code you requested",
    ("LEARNED_SKILLS", "learned_skills"): "to install, list, or undo an approved learned skill",
    ("GIT_REPO", "learned_skills"): "to create a local commit of the approved skill only",
    ("MIC_SPEAKER", "learned_skills"): "to hear your request and speak the skill reply",
    ("CLIPBOARD", "learned_skills"): "for the resource declared by this learned skill",
    ("SCREEN_FOCUS", "learned_skills"): "for the resource declared by this learned skill",
    ("NOTES_FILE", "learned_skills"): "for the resource declared by this learned skill",
    ("USER_CONFIG_FILE", "learned_skills"): "for the resource declared by this learned skill",
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
