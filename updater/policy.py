"""Classify file paths that Iris may propose to update."""

import os
import re

import config


TIER0_FILES = {
    "confirm.py", "config.py", "launcher.py", "requirements.txt", ".gitignore",
    ".env", ".env.example", "spec.md", "agents.md", "handoff.md",
}
TIER0_DIRS = {"updater", "tests", "stages", "data/backups"}
TIER1_ROOT_FILES = {"router.py", "main.py", "ai.py", "voice.py"}


def _relative_parts(path):
    """Normalize a relative project path without accepting parent traversal."""
    if not isinstance(path, str) or not path.strip():
        return None
    normalized = path.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[a-zA-Z]:", normalized):
        return None
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return parts


def _contains_symlink(relative_parts):
    """Refuse a project path when any component is a symbolic link."""
    current = os.path.abspath(config.PROJECT_FOLDER)
    if os.path.islink(current):
        return True
    for part in relative_parts:
        current = os.path.join(current, part)
        if os.path.islink(current):
            return True
    return False


def check_path(path):
    """Return tier0, tier1, or refused for one project-relative path."""
    parts = _relative_parts(path)
    if parts is None or _contains_symlink(parts):
        return "refused"
    relative = "/".join(parts).casefold()
    root = os.path.realpath(config.PROJECT_FOLDER)
    resolved = os.path.realpath(os.path.join(config.PROJECT_FOLDER, *parts))
    try:
        if os.path.commonpath([root, resolved]).casefold() != root.casefold():
            return "refused"
    except ValueError:
        return "refused"

    if relative in TIER0_FILES:
        return "tier0"
    if any(relative == directory or relative.startswith(directory + "/") for directory in TIER0_DIRS):
        return "tier0"
    if relative in TIER1_ROOT_FILES:
        return "tier1"
    if len(parts) == 2 and parts[0].casefold() == "iris" and parts[1].casefold().endswith(".py"):
        return "tier1"
    if len(parts) == 2 and parts[0].casefold() == "skills" and parts[1].casefold().endswith(".py"):
        return "tier1"
    return "refused"
