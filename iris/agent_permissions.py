"""Map known Jarvis commands to their logical resources using fixed rules."""

from iris.resources import KNOWN_RESOURCES
import config


def resources_for(command):
    """Return resources required by a known command without interpreting copied data."""
    text = command.lower().strip()
    if text.startswith("explain this code") or text.startswith("fix this code"):
        return ["CLIPBOARD", "SCREEN_FOCUS", "API_QUOTA"]
    if text.startswith("save my work to github"):
        return ["GIT_REPO"]  # PROTECTED
    if text.startswith("take a note"):
        return ["NOTES_FILE"]
    if text.startswith(("add app ", "add website ", "remove app ", "remove website ")):
        return ["USER_CONFIG_FILE"]
    if text.startswith("add a skill that ") or text.startswith("change skill ") or text in {"list skills", "undo last skill"}:
        resources = ["LEARNED_SKILLS"]
        if text.startswith("add a skill that ") or text.startswith("change skill "):
            resources.extend(["API_QUOTA", "GIT_REPO"])
        elif text == "undo last skill":
            resources.append("GIT_REPO")
        return resources
    from skills.learned_skills import resources_for_command
    learned_resources = resources_for_command(command)
    if learned_resources is not None:
        return learned_resources
    if text in {"list apps", "list websites"}:
        return []
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
    return resources, all(resource in KNOWN_RESOURCES for resource in resources)  # PROTECTED
