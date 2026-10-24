"""Save project changes to GitHub after typed confirmations."""

import logging
import os
import subprocess

import config
from confirm import ask_yes_no
from dotenv import load_dotenv


def _run_git(arguments):
    """Run one fixed Git command in the approved project directory."""
    # List arguments and a fixed working folder prevent shell interpretation of user text.
    result = subprocess.run(
        ["git"] + arguments,
        cwd=config.PROJECT_FOLDER,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    # Log only the fixed action and exit code so remote credentials cannot leak.
    logging.info("git_action=%s | result_code=%s", arguments[0], result.returncode)
    return result


def save_to_github():
    """Show changed files and require typed approval before each risky Git action."""
    try:
        status = _run_git(["status", "--short"])
    except Exception:
        return "I couldn't check Git status in the project folder."
    if status.returncode != 0:
        return f"Git status failed with exit code {status.returncode}. Check this project repository."

    changed_files = status.stdout.strip()
    if not changed_files:
        return "There are no project changes to save."
    print("Project changes:\n" + changed_files)
    if not ask_yes_no("Do you want to stage these project changes?", require_typed=True):
        return "I didn't stage or push anything."

    try:
        add_result = _run_git(["add", "-A"])
    except Exception:
        return "I couldn't stage the project changes."
    if add_result.returncode != 0:
        return f"Git add failed with exit code {add_result.returncode}."

    try:
        from iris.console import request_input
        message = (request_input("Commit message: ") or "").strip()
    except (EOFError, KeyboardInterrupt):
        # Keep an interrupted prompt from escaping and crashing the assistant loop.
        return "No commit message was entered. Changes are staged but not committed."
    if not message:
        return "No commit message was entered. Changes are staged but not committed."
    # Reject a secret in the commit message before it can enter Git history.
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key and api_key in message:
        return "I can't use a commit message that contains the configured Gemini API key."
    if not ask_yes_no(f"Commit the staged changes with this message: {message}?", require_typed=True):
        return "The changes remain staged; I didn't commit or push them."
    try:
        commit_result = _run_git(["commit", "-m", message])
    except Exception:
        return "I couldn't create the commit. The changes may still be staged."
    if commit_result.returncode != 0:
        return f"Git commit failed with exit code {commit_result.returncode}. The changes may still be staged."

    if not ask_yes_no("Do you want to push this commit to GitHub?", require_typed=True):
        return "The commit is saved locally; I didn't push it."
    try:
        push_result = _run_git(["push"])
    except Exception:
        return "I couldn't push to GitHub. The commit remains saved locally."
    if push_result.returncode != 0:
        return f"Git push failed with exit code {push_result.returncode}. Check your remote and GitHub login."
    return "Your changes were committed and pushed to GitHub."


def commit_learned_skill(slug, deleted=False):
    """Commit only one learned skill and its registry without pushing."""
    import re

    if not re.fullmatch(r"[a-z0-9_]+", slug):
        return False, "The learned-skill name is invalid."
    skill_path = f"skills/learned/{slug}.py"
    registry_path = "data/learned_skills.json"
    allowed_paths = {skill_path, registry_path}
    try:
        staged = _run_git(["diff", "--cached", "--name-only"])
        if staged.returncode != 0 or staged.stdout.strip():
            return False, "The Git index has unrelated staged changes; nothing was committed."
        if deleted:
            add_result = _run_git(["add", "-A", "--", skill_path, registry_path])
        else:
            add_result = _run_git(["add", "-f", "--", skill_path, registry_path])
        if add_result.returncode != 0:
            return False, "Git could not stage the approved skill files."
        staged = _run_git(["diff", "--cached", "--name-only"])
        staged_paths = {line.strip().replace("\\", "/") for line in staged.stdout.splitlines() if line.strip()}
        if staged.returncode != 0 or staged_paths != allowed_paths:
            _run_git(["reset", "--", skill_path, registry_path])
            return False, "Git staged an unexpected file; no commit was made."
        commit = _run_git(["commit", "-m", f"Learned skill: {slug}"])
        if commit.returncode != 0:
            _run_git(["reset", "--", skill_path, registry_path])
            return False, "The local learned-skill commit failed."
    except Exception:
        return False, "The fixed local Git operation failed safely."
    return True, "Committed locally; nothing was pushed."
