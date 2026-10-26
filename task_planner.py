"""Validate fixed-skill plans and run approved steps in order."""

from dataclasses import dataclass, field
import json
import re

import ai
import config
import skills
import skill_development


MAX_STEPS = 8
MAX_NOTE_LENGTH = 2000
SKILL_PERMISSIONS = {
    "open_target": "open the approved app or website",
    "save_note": "save this note",
    "delete_note": "delete the selected note",
    "research_web": "send this query to Gemini Search",
    "create_skill_proposal": "ask the configured AI to draft a skill proposal",
    "approve_skill_proposal": "after preview, ask typed approval for manual integration",
    "withdraw_skill_proposal": "after preview, ask typed approval to withdraw the proposal",
}
SKILL_SCHEMAS = {
    "open_target": {"target"}, "tell_time": set(), "tell_date": set(),
    "save_note": {"text"}, "list_notes": set(), "search_notes": {"query"},
    "delete_note": {"index"}, "chat": {"message"}, "help": set(),
    "research_web": {"query"}, "create_skill_proposal": {"name", "purpose"},
    "approve_skill_proposal": {"name", "version"}, "withdraw_skill_proposal": {"name", "version"},
}
ACTION_WORDS = ("open ", "launch ", "start ", "visit ", "save ", "note ", "search ", "find ", "research ", "propose skill ", "draft skill ", "delete ", "remove ", "tell ", "show ", "do ", "help me ")


@dataclass
class PlanStep:
    """Hold one validated skill call and its execution result."""

    step_id: str
    skill: str
    params: dict
    depends_on: list = field(default_factory=list)
    permission: str = "none"
    status: str = "pending"
    result: str = ""


def _normalized(text):
    """Normalize whitespace and capitalization for local matching."""
    return " ".join(str(text or "").strip().lower().split())


def _open_target(text):
    """Extract the requested target from a common open command."""
    cleaned = _normalized(text)
    cleaned = re.sub(r"^(?:please\s+)?(?:can you|could you|would you)\s+", "", cleaned)
    cleaned = re.sub(r"^(?:please\s+)?", "", cleaned)
    match = re.fullmatch(r"(?:open|launch|start|visit|go to)\s+(?:the\s+)?(.+?)(?:\s+for me)?[.!?]*", cleaned)
    return match.group(1).strip(" .!?'\"") if match else None


def _known_parts(command):
    """Split only clear, supported local command sequences."""
    separators = (
        r",\s*(?:and\s+)?(?=(?:(?:please\s+)?(?:can you|could you)\s+)?(?:open|launch|start|visit|go to|tell me the time|what time|time\b|what is the date|date\b|note\b|take a note|save a note|show notes|search notes|delete note|help\b))",
        r"\s+and then\s+", r"\s+then\s+",
        r"\s+and\s+(?=(?:(?:please\s+)?(?:can you|could you)\s+)?(?:open|launch|start|visit|go to|tell me the time|what time|time\b|what is the date|date\b|note\b|take a note|save a note|show notes|search notes|delete note|help\b))",
    )
    for separator in separators:
        parts = re.split(separator, command, flags=re.IGNORECASE)
        if len(parts) > 1 and all(_parse_local(part) is not None for part in parts):
            return parts
    return []


def _parse_local(command):
    """Turn one clearly phrased command into a fixed registered skill call."""
    text = str(command or "").strip()
    normalized = _normalized(text).rstrip(".!?")
    if normalized in {"time", "what time is it", "what's the time", "tell me the time"}:
        return "tell_time", {}
    if normalized in {"date", "what is the date", "what's the date", "what day is it"}:
        return "tell_date", {}
    if normalized in {"help", "what can you do", "what can iris do", "list your capabilities"}:
        return "help", {}
    if normalized in {"show notes", "show my notes", "read my notes", "list notes"}:
        return "list_notes", {}
    match = re.fullmatch(r"(?:search|find) notes(?: for| about)?\s+(.+)", text, re.IGNORECASE)
    if match:
        return "search_notes", {"query": match.group(1).strip().strip(".?!")}
    match = re.fullmatch(r"(?:delete|remove) note\s+(\d+)", text, re.IGNORECASE)
    if match:
        return "delete_note", {"index": int(match.group(1))}
    match = re.fullmatch(r"(?:research|search the web for|search web for)\s+(.+)", text, re.IGNORECASE)
    if match:
        return "research_web", {"query": match.group(1).strip().strip(".?!")}
    match = re.fullmatch(r"(?:propose|draft) skill\s+([a-z][a-z0-9_]{1,30})\s+(?:for|to)\s+(.+)", text, re.IGNORECASE)
    if match:
        return "create_skill_proposal", {"name": match.group(1).lower(), "purpose": match.group(2).strip()}
    match = re.fullmatch(r"(approve|withdraw) proposal\s+([a-z][a-z0-9_]{1,30})\s+v?(\d+)", text, re.IGNORECASE)
    if match:
        skill_name = "approve_skill_proposal" if match.group(1).lower() == "approve" else "withdraw_skill_proposal"
        return skill_name, {"name": match.group(2).lower(), "version": int(match.group(3))}
    match = re.fullmatch(r"(?:note|take a note|save a note)\s+(.+)", text, re.IGNORECASE)
    if match:
        return "save_note", {"text": match.group(1).strip()}
    target = _open_target(text)
    if target and (target in config.APPS or target in config.WEBSITES):
        return "open_target", {"target": target}
    if target:
        return "unsupported_open", {"target": target}
    return None


def _validate_step(step_data, index, prior_ids):
    """Validate one model-proposed step against the fixed skill schemas."""
    if not isinstance(step_data, dict) or set(step_data) != {"id", "skill", "params", "depends_on"}:
        raise ValueError("Each step must contain only id, skill, params, and depends_on.")
    step_id = step_data["id"]
    skill_name = step_data["skill"]
    params = step_data["params"]
    dependencies = step_data["depends_on"]
    if not isinstance(step_id, str) or step_id != f"step_{index + 1}":
        raise ValueError("Step IDs must follow the order step_1, step_2, and so on.")
    if not isinstance(skill_name, str) or skill_name not in SKILL_SCHEMAS:
        raise ValueError(f"Unregistered skill in {step_id}.")
    if not isinstance(params, dict) or not isinstance(dependencies, list):
        raise ValueError(f"Invalid parameters or dependencies in {step_id}.")
    if any(not isinstance(item, str) or item not in prior_ids for item in dependencies):
        raise ValueError(f"Dependencies in {step_id} must refer to earlier steps.")
    if len(set(dependencies)) != len(dependencies):
        raise ValueError(f"Duplicate dependency in {step_id}.")

    exact = SKILL_SCHEMAS[skill_name]
    if set(params) != exact:
        raise ValueError(f"Invalid parameters for {skill_name}.")
    if skill_name == "open_target":
        target = params["target"]
        if not isinstance(target, str) or target not in config.APPS and target not in config.WEBSITES:
            raise ValueError("The target is not on Iris's approved app or website list.")
    elif skill_name in {"save_note", "search_notes", "chat"}:
        key = {"save_note": "text", "search_notes": "query", "chat": "message"}[skill_name]
        value = params[key]
        maximum = MAX_NOTE_LENGTH if key == "text" else 4000
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"Invalid {key} value in {step_id}.")
    elif skill_name == "research_web":
        query = params["query"]
        if not isinstance(query, str) or len(query.strip()) < 3 or len(query) > 500:
            raise ValueError(f"Invalid query value in {step_id}.")
    elif skill_name == "create_skill_proposal":
        name = params["name"]
        purpose = params["purpose"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name):
            raise ValueError(f"Invalid proposal name in {step_id}.")
        if not isinstance(purpose, str) or len(purpose.strip()) < 10 or len(purpose) > 500:
            raise ValueError(f"Invalid proposal purpose in {step_id}.")
    elif skill_name in {"approve_skill_proposal", "withdraw_skill_proposal"}:
        name = params["name"]
        version = params["version"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name):
            raise ValueError(f"Invalid proposal name in {step_id}.")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError(f"Invalid proposal version in {step_id}.")
    elif skill_name == "delete_note":
        note_index = params["index"]
        if isinstance(note_index, bool) or not isinstance(note_index, int) or note_index < 1:
            raise ValueError("A note number must be a positive integer.")
    permission = SKILL_PERMISSIONS.get(skill_name, "none")
    if skill_name == "delete_note":
        permission = f"delete note {params['index']}"
    elif skill_name == "research_web":
        permission = "send this query to Gemini Search"
    elif skill_name == "create_skill_proposal":
        permission = f"ask AI to draft the {params['name']} skill proposal"
    elif skill_name in {"approve_skill_proposal", "withdraw_skill_proposal"}:
        permission = f"after-preview: {permission} for {params['name']} v{params['version']}"
    return PlanStep(step_id, skill_name, params, dependencies, permission)


def validate_plan(payload):
    """Validate a whole serialized plan before any action can run."""
    if not isinstance(payload, dict) or set(payload) != {"steps"} or not isinstance(payload["steps"], list):
        raise ValueError("A plan must be a JSON object containing only a steps list.")
    raw_steps = payload["steps"]
    if not raw_steps or len(raw_steps) > MAX_STEPS:
        raise ValueError(f"A plan must contain between 1 and {MAX_STEPS} steps.")
    result = []
    prior_ids = set()
    for index, step_data in enumerate(raw_steps):
        step = _validate_step(step_data, index, prior_ids)
        result.append(step)
        prior_ids.add(step.step_id)
    if any(step.skill == "research_web" for step in result) and any(step.skill == "save_note" for step in result):
        raise ValueError("Inspect the research report first, then ask Iris to save the exact note you choose.")
    return result


def _model_plan(command):
    """Ask the configured model for data that will be validated before use."""
    response = ai.plan_request(command)
    if not isinstance(response, str):
        raise ValueError("The AI planner returned no text plan.")
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return validate_plan(json.loads(text, object_pairs_hook=_unique_object))


def _unique_object(pairs):
    """Reject duplicate JSON keys so ambiguous model output cannot pass validation."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("The AI plan contains a duplicate JSON field.")
        result[key] = value
    return result


def _deterministic_plan(command):
    """Build plan steps locally for all supported, unambiguous commands."""
    text = str(command or "").strip()
    parts = _known_parts(text) or [text]
    parsed = [_parse_local(part) for part in parts]
    if len(parsed) > MAX_STEPS:
        raise ValueError(f"A plan may contain at most {MAX_STEPS} steps.")
    if any(item is None for item in parsed):
        return None
    unsupported = next((item for item in parsed if item[0] == "unsupported_open"), None)
    if unsupported:
        return "unsupported_open", unsupported[1]["target"]
    steps = []
    prior_ids = set()
    for index, (skill_name, params) in enumerate(parsed):
        raw_step = {"id": f"step_{index + 1}", "skill": skill_name, "params": params, "depends_on": []}
        step = _validate_step(raw_step, index, prior_ids)
        steps.append(step)
        prior_ids.add(step.step_id)
    return steps


def _looks_like_task(command):
    """Route action-like ambiguous requests to the constrained AI planner."""
    normalized = _normalized(command)
    return any(verb in normalized for verb in ACTION_WORDS)


def _approval(action, input_fn):
    """Require an exact typed yes before a consequential skill runs."""
    try:
        answer = input_fn(f"Iris wants to {action}. Type yes to approve, or anything else to cancel: ")
    except (EOFError, KeyboardInterrupt):
        return False
    return isinstance(answer, str) and answer.strip().casefold() == "yes"


def _describe_plan(steps):
    """Return a readable preview of every proposed step and dependency."""
    lines = ["Proposed plan:"]
    for index, step in enumerate(steps, 1):
        dependency_text = f"; after {', '.join(step.depends_on)}" if step.depends_on else ""
        permission_text = f"; approval: {step.permission}" if step.permission != "none" else "; no approval needed"
        lines.append(f"{index}. {step.skill} {step.params}{dependency_text}{permission_text}")
    return "\n".join(lines)


def _run_step(step, input_fn):
    """Run one already validated step using only a registered Python skill."""
    if step.skill == "open_target":
        return skills.open_approved(step.params["target"])
    if step.skill == "tell_time":
        return skills.tell_time()
    if step.skill == "tell_date":
        return skills.tell_date()
    if step.skill == "help":
        return skills.help_text()
    if step.skill == "save_note":
        return skills.add_note(step.params["text"])
    if step.skill == "list_notes":
        return skills.show_notes()
    if step.skill == "search_notes":
        return skills.search_notes(step.params["query"])
    if step.skill == "delete_note":
        return skills.delete_note(step.params["index"], approved=True)
    if step.skill == "research_web":
        return skills.research_web(step.params["query"])
    if step.skill == "create_skill_proposal":
        return skill_development.create_proposal(
            step.params["name"], step.params["purpose"], input_fn
        )
    if step.skill == "approve_skill_proposal":
        return skill_development.approve_for_manual_integration(
            step.params["name"], step.params["version"], input_fn
        )
    if step.skill == "withdraw_skill_proposal":
        return skill_development.withdraw_proposal(
            step.params["name"], step.params["version"], input_fn
        )
    if step.skill == "chat":
        return ai.ask(step.params["message"])
    raise ValueError("Unregistered skill.")


def _execute(steps, input_fn):
    """Approve all side effects, then execute while skipping failed dependencies."""
    # The complete plan was validated before this loop, so denial cannot leave partial work.
    for step in steps:
        if step.permission.startswith("after-preview:") or step.permission == "none":
            continue
        if not _approval(step.permission, input_fn):
            step.status = "denied"
            for remaining in steps:
                if remaining.status == "pending":
                    remaining.status = "skipped"
            return _summary(steps, cancelled=True)
    by_id = {step.step_id: step for step in steps}
    for step in steps:
        if any(by_id[dependency].status != "succeeded" for dependency in step.depends_on):
            step.status = "skipped"
            step.result = "Skipped because a required step did not succeed."
            continue
        step.status = "running"
        try:
            step.result = str(_run_step(step, input_fn))
            if step.result.startswith((
                "I couldn't", "I refused", "The notes file has", "Add some", "Use a research",
                "Web research", "Gemini ", "The configured Gemini", "I can't send a query",
                "Proposal was not saved", "Proposal validation failed",
            )):
                step.status = "failed"
            elif step.result.startswith(("Proposal creation denied", "Proposal approval denied", "Proposal withdrawal denied")):
                step.status = "denied"
            else:
                step.status = "succeeded"
        except Exception as error:
            step.status = "failed"
            if step.skill == "open_target":
                step.result = f"I couldn't open {step.params['target']}. Check its approved path."
            else:
                step.result = f"Step failed ({type(error).__name__})."
    return _summary(steps)


def _summary(steps, cancelled=False):
    """Report each step state and the final task outcome."""
    lines = []
    for index, step in enumerate(steps, 1):
        result = step.result or step.skill
        lines.append(f"{index}. {result} [{step.status}]")
    if cancelled:
        title = "Cancelled; no steps were run."
    else:
        succeeded = sum(step.status == "succeeded" for step in steps)
        failed = sum(step.status == "failed" for step in steps)
        skipped = sum(step.status == "skipped" for step in steps)
        title = f"Finished: {succeeded} succeeded, {failed} failed, {skipped} skipped."
    return title + "\n" + "\n".join(lines)


def handle(command, input_fn=input):
    """Route a request, validate its plan, and execute only approved registered skills."""
    text = str(command or "").strip()
    normalized = _normalized(text).rstrip(".!?")
    if not normalized:
        return "Type a question or command."
    if normalized in {"exit", "quit", "goodbye"}:
        return "Goodbye!"
    try:
        local = _deterministic_plan(text)
    except ValueError as error:
        return f"I can't safely use that command: {error} No steps were run."
    if isinstance(local, tuple) and local[0] == "unsupported_open":
        return f"{local[1]} is not on Iris's approved app or website list."
    if local is None:
        if not _looks_like_task(text):
            return ai.ask(text)
        try:
            local = _model_plan(text)
        except Exception as error:
            # Model output is untrusted; invalid or unavailable plans fail closed.
            detail = str(error) or type(error).__name__
            return f"I couldn't make a safe task plan: {detail} No steps were run."
    preview = _describe_plan(local)
    print(preview)
    result = _execute(local, input_fn)
    if len(local) == 1 and local[0].status == "succeeded":
        return local[0].result
    return result
