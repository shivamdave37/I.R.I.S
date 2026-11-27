"""Validate fixed-skill plans and run approved steps in order."""

from dataclasses import dataclass, field
import json
import re

import action_gateway
import ai
import config
import skills


MAX_STEPS = 8
MAX_NOTE_LENGTH = 2000
SKILL_PERMISSIONS = {
    # These strings appear in the preview; action_gateway owns authorization.
    "open_target": "open the approved app or website",
    "save_note": "save this note",
    "delete_note": "delete the selected note",
    "research_web": "send this query to the configured web-search provider",
    "create_skill_proposal": "ask the configured AI to draft a skill proposal",
    "approve_skill_proposal": "record manual-integration approval",
    "withdraw_skill_proposal": "withdraw the proposal",
    "open_search_result": "open the selected file or folder",
    "capture_screen": "capture one screen to temporary memory",
    "analyze_screen": "send the captured image to Gemini after a separate approval",
    "ui_click": "click one validated UI target",
    "ui_type": "replace text in one validated UI field",
    "add_task": "save this task",
    "complete_task": "mark task as completed",
    "delete_task": "delete the selected task",
    "set_timer": "set a timer",
    "copy_to_clipboard": "copy text to clipboard",
    "run_trial_skill": "run this trial skill in the isolated sandbox",
    "promote_trial_skill": "promote this trial skill to permanent status",
    "delete_trial_skill": "delete this trial skill from the registry",
    "add_trial_skill": "validate and add this trial skill to the isolated sandbox",
}
SKILL_SCHEMAS = {
    name: set(policy.parameter_names)
    for name, policy in action_gateway.ACTION_POLICIES.items()
}
ACTION_WORDS = (
    "open ", "launch ", "start ", "visit ", "save ", "note ", "search ", "find ", "research ",
    "propose skill ", "draft skill ", "delete ", "remove ", "tell ", "show ", "do ", "help me ",
    "click ", "type at ", "capture screen", "describe screen", "task ", "tasks", "todo",
    "timer", "remind", "battery", "system ", "weather", "clipboard", "trial ", "temp skill", "promote ",
    "add this to tr", "add to tr", "add this to trial", "add to trial"
)


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
    command_prefix_pattern = (
        r"(?:open|launch|start|visit|go to|tell me the time|what time|time\b|what is the date|date\b|"
        r"note\b|take a note|save a note|show notes|search notes|search files|search folder|search folders|"
        r"find files|find file|find folder|find folders|open result|delete note|help\b|"
        r"add task|new task|todo\b|tasks\b|show tasks|list tasks|complete task|delete task|"
        r"set timer|remind me|timers\b|show timers|system status|specs\b|battery\b|weather\b|"
        r"read clipboard|copy to clipboard|add this to tr|add to tr|add this to trial|add to trial|"
        r"trial skills|temp skills|dynamic skills)"
    )
    separators = (
        rf",\s*(?:and\s+)?(?=(?:(?:please\s+)?(?:can you|could you)\s+)?{command_prefix_pattern})",
        r"\s+and then\s+", r"\s+then\s+",
        rf"\s+and\s+(?=(?:(?:please\s+)?(?:can you|could you)\s+)?{command_prefix_pattern})",
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
    if normalized == "capture screen":
        return "capture_screen", {}
    if normalized in {"describe screen", "what is on screen", "what's on screen"}:
        import screen_capture
        frame = screen_capture.latest_frame()
        if frame is None:
            raise ValueError("Capture the screen first with 'capture screen'.")
        return "analyze_screen", {"frame_id": frame.frame_id, "question": "Describe the visible screen."}
    match = re.fullmatch(r"(?:describe|analyze) screen\s+(.+)", text, re.IGNORECASE)
    if match:
        import screen_capture
        frame = screen_capture.latest_frame()
        if frame is None:
            raise ValueError("Capture the screen first with 'capture screen'.")
        return "analyze_screen", {"frame_id": frame.frame_id, "question": match.group(1).strip()}
    match = re.fullmatch(r"click\s+(?:at\s+)?(\d+)\s*[, ]\s*(\d+)", text, re.IGNORECASE)
    if match:
        import screen_capture
        frame = screen_capture.latest_frame()
        if frame is None:
            raise ValueError("Capture the screen first with 'capture screen'.")
        return "ui_click", {"frame_id": frame.frame_id, "x": int(match.group(1)), "y": int(match.group(2))}
    match = re.fullmatch(r"type\s+at\s+(\d+)\s*[, ]\s*(\d+)\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if match:
        import screen_capture
        frame = screen_capture.latest_frame()
        if frame is None:
            raise ValueError("Capture the screen first with 'capture screen'.")
        return "ui_type", {
            "frame_id": frame.frame_id, "x": int(match.group(1)), "y": int(match.group(2)),
            "text": match.group(3),
        }
    if normalized in {"show notes", "show my notes", "read my notes", "list notes"}:
        return "list_notes", {}
    match = re.fullmatch(r"(?:search|find) notes(?: for| about)?\s+(.+)", text, re.IGNORECASE)
    if match:
        return "search_notes", {"query": match.group(1).strip().strip(".?!")}
    match = re.fullmatch(r"(?:search|find) (?:files?|folders?)(?: named| called| name| for)?\s+(.+)", text, re.IGNORECASE)
    if match:
        return "search_files", {"query": match.group(1).strip().strip(".?!")}
    match = re.fullmatch(r"open result\s+(\d+)", text, re.IGNORECASE)
    if match:
        return "open_search_result", {"index": int(match.group(1))}
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

    # Tasks
    if normalized in {"tasks", "show tasks", "list tasks", "my tasks", "todo", "todo list"}:
        return "list_tasks", {}
    match = re.fullmatch(r"(?:add task|new task|todo)\s+(.+)", text, re.IGNORECASE)
    if match:
        return "add_task", {"text": match.group(1).strip()}
    match = re.fullmatch(r"(?:complete|finish|done) task\s+(\d+)", text, re.IGNORECASE)
    if match:
        return "complete_task", {"index": int(match.group(1))}
    match = re.fullmatch(r"(?:delete|remove) task\s+(\d+)", text, re.IGNORECASE)
    if match:
        return "delete_task", {"index": int(match.group(1))}

    # Timers
    if normalized in {"timers", "show timers", "list timers", "active timers"}:
        return "list_timers", {}
    match = re.fullmatch(r"set (?:a )?timer for (\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)(?:\s*(?:for|to|:)\s*(.+))?", text, re.IGNORECASE)
    if match:
        val = int(match.group(1))
        unit = match.group(2).lower()
        msg = match.group(3) or "Timer finished!"
        multiplier = 60 if "min" in unit else (3600 if "h" in unit else 1)
        return "set_timer", {"seconds": val * multiplier, "message": msg.strip()}
    match = re.fullmatch(r"remind me in (\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\s*(?:to|for|:)\s*(.+)", text, re.IGNORECASE)
    if match:
        val = int(match.group(1))
        unit = match.group(2).lower()
        msg = match.group(3).strip()
        multiplier = 60 if "min" in unit else (3600 if "h" in unit else 1)
        return "set_timer", {"seconds": val * multiplier, "message": msg}

    # System Status & Battery
    if normalized in {"system status", "system info", "check system", "specs", "disk space"}:
        return "system_status", {}
    if normalized in {"battery", "battery status", "battery level", "power status"}:
        return "battery_status", {}

    # Weather
    match = re.fullmatch(r"(?:(?:what(?:'s| is) the )?weather(?: in\s+(.+)|$))", text, re.IGNORECASE)
    if match:
        loc = (match.group(1) or "").strip().strip("?.!")
        return "get_weather", {"location": loc}

    # Clipboard
    if normalized in {"read clipboard", "show clipboard", "clipboard", "get clipboard"}:
        return "read_clipboard", {}
    match = re.fullmatch(r"copy to clipboard:?\s+(.+)", text, re.IGNORECASE)
    if match:
        return "copy_to_clipboard", {"text": match.group(1).strip()}

    # Dynamic & Trial Skills
    if normalized in {"trial skills", "show trial skills", "list trial skills", "temp skills", "list temp skills", "dynamic skills"}:
        return "list_trial_skills", {}
    if normalized in {"add this to tr", "add to tr", "add this to trial", "add to trial", "add trial skill"}:
        raise ValueError("Specify the skill to add, e.g.: 'add this to tr <name> for <purpose>' or 'add this to tr: <task>'.")
    add_trial_match = re.match(
        r"^(?:add\s+(?:this\s+)?to\s+(?:trial|tr)|add\s+trial\s+skill)\s*(?::\s*|\s+)(.+)$",
        text,
        re.IGNORECASE
    )
    if add_trial_match:
        rest = add_trial_match.group(1).strip()
        sub = re.match(r"^([a-zA-Z0-9_-]{2,30})\s+(?:for|to|:)\s+(.+)$", rest, re.IGNORECASE)
        if sub:
            skill_name = sub.group(1).strip().lower()
            purpose = sub.group(2).strip()
        else:
            words = re.sub(r"[^a-zA-Z0-9\s_]", "", rest).split()
            if len(words) >= 2:
                skill_name = "_".join(words[:3]).lower()
            elif words:
                skill_name = words[0].lower()
            else:
                skill_name = "custom_trial_skill"
            purpose = rest
        return "add_trial_skill", {"name": skill_name, "purpose": purpose}
    match = re.fullmatch(r"(?:run|execute)\s+(?:trial|temp skill)\s*(?::\s*|\s+)(.+)", text, re.IGNORECASE)
    if match:
        return "run_trial_skill", {"skill_id": match.group(1).strip()}
    match = re.fullmatch(r"promote\s+(?:trial|skill)\s*(?::\s*|\s+)(.+)", text, re.IGNORECASE)
    if match:
        return "promote_trial_skill", {"skill_id": match.group(1).strip()}
    match = re.fullmatch(
        r"(?:delete|remove|discard)\s+(?:(?:this\s+)?(?:from\s+)?(?:trial|temp skill)|trial\s+skill)\s*(?::\s*|\s+)(.+)",
        text,
        re.IGNORECASE
    )
    if match:
        return "delete_trial_skill", {"skill_id": match.group(1).strip()}

    target = _open_target(text)
    if target and (target in config.APPS or target in config.WEBSITES):
        return "open_target", {"target": target}

    # Fast-retrieval pathway: check if an existing trial skill matches this command
    try:
        import dynamic_skills
        trial_match = dynamic_skills.find_matching_trial_skill(text)
        if trial_match:
            return "run_trial_skill", {"skill_id": trial_match["skill_id"]}
    except Exception:
        pass

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
    action_gateway.validate_policy(skill_name, params)
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
    elif skill_name == "search_files":
        query = params["query"]
        if (not isinstance(query, str) or not query.strip() or len(query) > skills.MAX_FILE_SEARCH_QUERY_LENGTH
                or "/" in query or "\\" in query or query.strip() in {".", ".."}):
            raise ValueError(f"Invalid file search query in {step_id}.")
    elif skill_name == "open_search_result":
        result_index = params["index"]
        if isinstance(result_index, bool) or not isinstance(result_index, int) or result_index < 1:
            raise ValueError("A search result number must be a positive integer.")
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
    elif skill_name == "add_task":
        task_text = params["text"]
        if not isinstance(task_text, str) or not task_text.strip() or len(task_text) > MAX_NOTE_LENGTH:
            raise ValueError(f"Task text must be 1 to {MAX_NOTE_LENGTH} characters.")
    elif skill_name in {"complete_task", "delete_task"}:
        task_index = params["index"]
        if isinstance(task_index, bool) or not isinstance(task_index, int) or task_index < 1:
            raise ValueError("A task number must be a positive integer.")
    elif skill_name == "set_timer":
        seconds = params["seconds"]
        message = params["message"]
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 1 or seconds > 86400:
            raise ValueError("Timer seconds must be between 1 and 86400.")
        if not isinstance(message, str) or not message.strip() or len(message) > 500:
            raise ValueError("Timer message must be 1 to 500 characters.")
    elif skill_name == "get_weather":
        loc = params["location"]
        if not isinstance(loc, str) or len(loc) > 100:
            raise ValueError("Weather location must be at most 100 characters.")
    elif skill_name == "copy_to_clipboard":
        clip_text = params["text"]
        if not isinstance(clip_text, str) or not clip_text.strip() or len(clip_text) > 5000:
            raise ValueError("Clipboard text must be 1 to 5000 characters.")
    elif skill_name in {"run_trial_skill", "promote_trial_skill", "delete_trial_skill"}:
        sid = params.get("skill_id")
        if not isinstance(sid, str) or not sid.strip() or len(sid) > 100:
            raise ValueError(f"Skill ID must be 1 to 100 characters in {step_id}.")
    permission = SKILL_PERMISSIONS.get(skill_name, "none")
    if skill_name == "delete_note":
        permission = f"delete note {params['index']}"
    elif skill_name == "complete_task":
        permission = f"mark task {params['index']} as completed"
    elif skill_name == "delete_task":
        permission = f"delete task {params['index']}"
    elif skill_name == "set_timer":
        permission = f"set a timer for {params['seconds']} seconds"
    elif skill_name in {"list_tasks", "list_timers", "system_status", "battery_status", "get_weather", "read_clipboard", "list_trial_skills"}:
        permission = "none"
    elif skill_name == "run_trial_skill":
        permission = f"run trial skill {params['skill_id']!r} in the isolated sandbox"
    elif skill_name == "promote_trial_skill":
        permission = f"promote trial skill {params['skill_id']!r} to permanent status"
    elif skill_name == "delete_trial_skill":
        permission = f"delete trial skill {params['skill_id']!r}"
    elif skill_name == "research_web":
        permission = "send this query to the configured web-search provider"
    elif skill_name == "search_files":
        permission = "none"
    elif skill_name == "open_search_result":
        permission = "open the selected search result"
    elif skill_name == "create_skill_proposal":
        permission = f"ask AI to draft the {params['name']} skill proposal"
    elif skill_name in {"approve_skill_proposal", "withdraw_skill_proposal"}:
        permission = f"{permission} for {params['name']} v{params['version']} (a second typed approval follows the proposal preview)"
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
    latest_search_id = None
    for step in result:
        if step.skill == "search_files":
            latest_search_id = step.step_id
        elif step.skill == "open_search_result" and latest_search_id is not None:
            if latest_search_id not in step.depends_on:
                raise ValueError("Opening a result in the same plan must depend on its file-search step.")
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
    plan = validate_plan(json.loads(text, object_pairs_hook=_unique_object))
    if any(step.skill in {"capture_screen", "analyze_screen", "ui_click", "ui_type"} for step in plan):
        raise ValueError("Screen and UI actions must come from explicit local commands.")
    return plan


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
        dependencies = [steps[-1].step_id] if skill_name == "open_search_result" and steps and steps[-1].skill == "search_files" else []
        raw_step = {"id": f"step_{index + 1}", "skill": skill_name, "params": params, "depends_on": dependencies}
        step = _validate_step(raw_step, index, prior_ids)
        steps.append(step)
        prior_ids.add(step.step_id)
    return steps


def _looks_like_task(command):
    """Route action-like ambiguous requests to the constrained AI planner."""
    normalized = _normalized(command)
    return any(verb in normalized for verb in ACTION_WORDS)


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
    return action_gateway.execute(step.skill, step.params, input_fn)


def _execute(steps, input_fn):
    """Dispatch each step through the gateway, which asks just before actions."""
    by_id = {step.step_id: step for step in steps}
    for step in steps:
        if any(by_id[dependency].status != "succeeded" for dependency in step.depends_on):
            step.status = "skipped"
            step.result = "Skipped because a required step did not succeed."
            continue
        step.status = "running"
        try:
            step.result = str(_run_step(step, input_fn))
            if step.result.startswith("UI action unverified:"):
                step.status = "unverified"
            elif step.result.startswith((
                "I couldn't", "I refused", "The notes file has", "Add some", "Use a research",
                "Web research", "Gemini ", "Tavily ", "The configured Gemini", "I can't send a query",
                "Proposal was not saved", "Proposal validation failed", "File search is unavailable",
                "File search reached its safety limit", "I couldn't open the selected",
                "The selected path changed after approval", "I couldn't request Windows to open",
                "That file-search result is no longer available",
                "Opening selected files or folders is supported only on Windows",
                "Screen capture unavailable",
                "Screen analysis failed", "Screen analysis is not configured",
                "Screen analysis is unavailable", "UI click failed", "UI typing failed",
                "Gemini vision", "Gemini rejected the key or image", "The configured Gemini model may",
                "Gemini screen analysis", "I couldn't reach Gemini for screen analysis",
                "Gemini returned an unexpected screen-analysis",
            )):
                step.status = "failed"
            elif step.result.startswith(("Proposal creation denied", "Proposal approval denied", "Proposal withdrawal denied")):
                step.status = "denied"
            elif step.result.startswith("Refused:"):
                step.status = "refused"
            else:
                step.status = "succeeded"
        except action_gateway.ApprovalDenied as error:
            step.status = "denied"
            step.result = str(error)
            for remaining in steps:
                if remaining.status == "pending":
                    remaining.status = "skipped"
                    remaining.result = remaining.skill
            return _summary(steps, cancelled=True)
        except action_gateway.InvalidAction as error:
            step.status = "failed"
            step.result = str(error)
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
        ran = any(step.status in {"succeeded", "failed", "unverified"} for step in steps)
        title = "Cancelled; remaining steps were not run." if ran else "Cancelled; no steps were run."
    else:
        succeeded = sum(step.status == "succeeded" for step in steps)
        failed = sum(step.status == "failed" for step in steps)
        skipped = sum(step.status == "skipped" for step in steps)
        unverified = sum(step.status == "unverified" for step in steps)
        refused = sum(step.status == "refused" for step in steps)
        refused_part = f", {refused} refused" if refused else ""
        title = f"Finished: {succeeded} succeeded, {failed} failed, {skipped} skipped, {unverified} unverified{refused_part}."
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
    if len(local) == 1 and local[0].status in {"succeeded", "refused"}:
        return local[0].result
    return result
