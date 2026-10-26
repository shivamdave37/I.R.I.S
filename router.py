"""Route common requests quickly and send ordinary questions straight to chat."""

import re

import config
import skills
import ai
import task_planner


def normalize(text):
    """Lowercase text and collapse whitespace while keeping useful app punctuation."""
    return " ".join(str(text or "").strip().lower().split())


def _open_target(text):
    """Recognize natural open requests and return an approved target name."""
    cleaned = normalize(text)
    cleaned = re.sub(r"^(?:please\s+)?(?:can you|could you|would you)\s+", "", cleaned)
    cleaned = re.sub(r"^(?:please\s+)?", "", cleaned)
    match = re.fullmatch(r"(?:open|launch|start|visit|go to)\s+(?:the\s+)?(.+?)(?:\s+for me)?[.!?]*", cleaned)
    if not match:
        return None
    target = match.group(1).strip(" .!?'")
    return target


def _approval(action, input_fn):
    """Require an explicit typed yes before a local side effect."""
    try:
        answer = input_fn(f"Iris wants to {action}. Type yes to approve, or anything else to cancel: ")
    except EOFError:
        return False
    return isinstance(answer, str) and answer.strip().casefold() == "yes"


def _single_command(command, input_fn, approved=False):
    """Handle one supported local command or send it directly to chat."""
    text = str(command or "").strip()
    normalized = normalize(text).rstrip(".!?")
    if not normalized:
        return "Type a question or command."
    if normalized in {"exit", "quit", "goodbye"}:
        return "Goodbye!"
    if normalized in {"help", "what can you do", "what can iris do", "list your capabilities"}:
        return skills.help_text()
    if normalized in {"time", "what time is it", "what's the time", "tell me the time"}:
        return skills.tell_time()
    if normalized in {"date", "what is the date", "what's the date", "what day is it"}:
        return skills.tell_date()
    target = _open_target(text)
    if target:
        if target not in config.APPS and target not in config.WEBSITES:
            return f"{target} is not on Iris's approved app or website list."
        if not approved and not _approval(f"open approved target {target}", input_fn):
            return "Cancelled; nothing was opened."
        try:
            return skills.open_approved(target)
        except Exception:
            return f"I couldn't open {target}. Check its approved path."
    note_match = re.fullmatch(r"(?:note|take a note)\s+(.+)", text, re.IGNORECASE)
    if note_match:
        note = note_match.group(1).strip()
        if not note:
            return "Add some text after 'note'."
        if not approved and not _approval("save this note", input_fn):
            return "Cancelled; nothing was saved."
        return skills.add_note(note)
    if normalized in {"show notes", "show my notes", "read my notes"}:
        return skills.show_notes()
    # Unknown requests go straight to chat; there is no separate AI planner call.
    return ai.ask(text)


def _is_known_local_command(command):
    """Check whether a phrase is a supported local step without running it."""
    normalized = normalize(command).rstrip(".!?")
    if normalized in {
        "help", "what can you do", "what can iris do", "list your capabilities",
        "time", "what time is it", "what's the time", "tell me the time",
        "date", "what is the date", "what's the date", "what day is it",
        "show notes", "show my notes", "read my notes",
    }:
        return True
    target = _open_target(command)
    if target:
        return target in config.APPS or target in config.WEBSITES
    return re.fullmatch(r"(?:note|take a note)\s+.+", command.strip(), re.IGNORECASE) is not None


def _multi_action_parts(command):
    """Split only when every part is already a supported local command."""
    separators = (
        r"\s+and then\s+",
        r"\s+then\s+",
        r"\s+and\s+(?=(?:(?:please\s+)?(?:can you|could you)\s+)?(?:open|launch|start|visit|go to|tell me the time|what time|time\b|what is the date|date\b|note\b|take a note|show notes|help\b))",
    )
    for separator in separators:
        parts = re.split(separator, command, flags=re.IGNORECASE)
        if len(parts) > 1 and all(_is_known_local_command(part) for part in parts):
            return parts
    return []


def _approval_for_command(command):
    """Describe the approval needed for a supported side-effecting command."""
    target = _open_target(command)
    if target:
        return f"open approved target {target}"
    if re.fullmatch(r"(?:note|take a note)\s+.+", command.strip(), re.IGNORECASE):
        return "save this note"
    return None


def handle(command, input_fn=input):
    """Route requests through the structured plan and execution path."""
    return task_planner.handle(command, input_fn)
