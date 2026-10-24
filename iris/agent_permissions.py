"""Map known Jarvis commands to their logical resources using fixed rules."""

from iris.resources import KNOWN_RESOURCES


def resources_for(command):
    """Return resources required by a known command without interpreting copied data."""
    text = command.lower().strip()
    if text.startswith("explain this code") or text.startswith("fix this code"):
        return ["CLIPBOARD", "SCREEN_FOCUS", "API_QUOTA", "MIC_SPEAKER"]
    if text.startswith("save my work to github"):
        return ["GIT_REPO"]
    if text.startswith("take a note"):
        return ["NOTES_FILE"]
    if text == "show my notes":
        return ["NOTES_FILE"]
    if text.startswith("open "):
        return ["SCREEN_FOCUS"]
    if text in {"news", "latest news", "tell me the news"}:
        return ["API_QUOTA", "MIC_SPEAKER"]
    if text in {"time", "what's the time", "date", "what's the date", "exit", "quit"}:
        return []
    return ["API_QUOTA", "MIC_SPEAKER"]


def inspect(command):
    """Return the fixed resource list and refuse any unknown resource name."""
    resources = resources_for(command)
    return resources, all(resource in KNOWN_RESOURCES for resource in resources)
