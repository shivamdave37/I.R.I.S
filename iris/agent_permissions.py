"""Map known Jarvis commands to their logical resources using fixed rules."""

from iris.resources import KNOWN_RESOURCES
import config


def resources_for(command):
    """Return resources required by a known command without interpreting copied data."""
    text = command.lower().strip()
    if text.startswith("explain this code") or text.startswith("fix this code"):
        return ["CLIPBOARD", "SCREEN_FOCUS", "API_QUOTA"]
    if text.startswith("save my work to github"):
        return ["GIT_REPO"]
    if text.startswith("take a note"):
        return ["NOTES_FILE"]
    if text == "show my notes":
        return ["NOTES_FILE"]
    if text.startswith("my name is ") or text.startswith("remember i prefer ") or text in {"my name", "what is my name", "what do you remember about me"}:
        return ["NOTES_FILE"]
    if text.startswith("open "):
        return ["SCREEN_FOCUS"]
    if text in {"news", "latest news", "tell me the news"}:
        return ["API_QUOTA"]
    if text in {"time", "what's the time", "date", "what's the date", "exit", "quit"}:
        return []
    return ["API_QUOTA"]


def inspect(command):
    """Return the fixed resource list and refuse any unknown resource name."""
    resources = resources_for(command)
    mode = getattr(config, "MODE", "typed")
    if isinstance(mode, str) and mode.strip().lower() in {"voice", "both"}:
        # Voice tasks share the microphone and speaker as one exclusive resource.
        resources = sorted(set(resources) | {"MIC_SPEAKER"})
    return resources, all(resource in KNOWN_RESOURCES for resource in resources)
