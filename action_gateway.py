"""Validate, approve, and dispatch every registered Iris skill."""

from dataclasses import dataclass
from contextlib import nullcontext
import json
import math
import re

import approval_context
import ai
import config
import skills
import skill_development


@dataclass(frozen=True)
class ActionPolicy:
    """Describe the exact parameter keys and approval rule for one skill."""

    parameter_names: frozenset
    effect: str
    requires_approval: bool


STATE_CHANGING_ACTIONS = frozenset({
    "open_target", "save_note", "delete_note", "create_skill_proposal",
    "approve_skill_proposal", "withdraw_skill_proposal", "open_search_result",
    "capture_screen", "ui_click", "ui_type",
    "add_task", "complete_task", "delete_task", "set_timer", "copy_to_clipboard",
    "run_trial_skill", "promote_trial_skill", "delete_trial_skill",
})
# This closed list is the only set allowed to skip a typed action approval.
NO_APPROVAL_ACTIONS = frozenset({
    "tell_time", "tell_date", "list_notes", "search_notes", "chat", "help", "search_files",
    "list_tasks", "list_timers", "system_status", "battery_status", "get_weather", "read_clipboard",
    "list_trial_skills",
})
MAX_NOTE_LENGTH = 2000
MAX_CHAT_LENGTH = 4000


class ApprovalDenied(Exception):
    """Signal that the user did not approve this individual action."""


class InvalidAction(ValueError):
    """Signal an unknown action or a missing/invalid fail-closed policy."""


ACTION_POLICIES = {
    "open_target": ActionPolicy(frozenset({"target"}), "state_change", True),
    "tell_time": ActionPolicy(frozenset(), "read_only", False),
    "tell_date": ActionPolicy(frozenset(), "read_only", False),
    "save_note": ActionPolicy(frozenset({"text"}), "state_change", True),
    "list_notes": ActionPolicy(frozenset(), "read_only", False),
    "search_notes": ActionPolicy(frozenset({"query"}), "read_only", False),
    "delete_note": ActionPolicy(frozenset({"index"}), "state_change", True),
    "chat": ActionPolicy(frozenset({"message"}), "external_request", False),
    "help": ActionPolicy(frozenset(), "read_only", False),
    "research_web": ActionPolicy(frozenset({"query"}), "external_request", True),
    "create_skill_proposal": ActionPolicy(frozenset({"name", "purpose"}), "state_change", True),
    "approve_skill_proposal": ActionPolicy(frozenset({"name", "version"}), "state_change", True),
    "withdraw_skill_proposal": ActionPolicy(frozenset({"name", "version"}), "state_change", True),
    "search_files": ActionPolicy(frozenset({"query"}), "read_only", False),
    "open_search_result": ActionPolicy(frozenset({"index"}), "state_change", True),
    "capture_screen": ActionPolicy(frozenset(), "state_change", True),
    "analyze_screen": ActionPolicy(frozenset({"frame_id", "question"}), "external_request", True),
    "ui_click": ActionPolicy(frozenset({"frame_id", "x", "y"}), "state_change", True),
    "ui_type": ActionPolicy(frozenset({"frame_id", "text", "x", "y"}), "state_change", True),
    "add_task": ActionPolicy(frozenset({"text"}), "state_change", True),
    "list_tasks": ActionPolicy(frozenset(), "read_only", False),
    "complete_task": ActionPolicy(frozenset({"index"}), "state_change", True),
    "delete_task": ActionPolicy(frozenset({"index"}), "state_change", True),
    "set_timer": ActionPolicy(frozenset({"seconds", "message"}), "state_change", True),
    "list_timers": ActionPolicy(frozenset(), "read_only", False),
    "system_status": ActionPolicy(frozenset(), "read_only", False),
    "battery_status": ActionPolicy(frozenset(), "read_only", False),
    "get_weather": ActionPolicy(frozenset({"location"}), "external_request", False),
    "read_clipboard": ActionPolicy(frozenset(), "read_only", False),
    "copy_to_clipboard": ActionPolicy(frozenset({"text"}), "state_change", True),
    "list_trial_skills": ActionPolicy(frozenset(), "read_only", False),
    "run_trial_skill": ActionPolicy(frozenset({"skill_id"}), "state_change", True),
    "promote_trial_skill": ActionPolicy(frozenset({"skill_id"}), "state_change", True),
    "delete_trial_skill": ActionPolicy(frozenset({"skill_id"}), "state_change", True),
}


def _policy_for(skill_name, params):
    """Require a registered policy with a valid Boolean approval decision."""
    if not isinstance(skill_name, str):
        raise InvalidAction("The requested action name is invalid.")
    policy = ACTION_POLICIES.get(skill_name)
    if (not isinstance(policy, ActionPolicy) or type(policy.requires_approval) is not bool
            or not isinstance(policy.parameter_names, frozenset)
            or not isinstance(policy.effect, str)
            or policy.effect not in {"read_only", "external_request", "state_change"}):
        raise InvalidAction("This skill has no valid approval policy; it was refused.")
    if skill_name in STATE_CHANGING_ACTIONS and policy.effect != "state_change":
        raise InvalidAction("This skill has no valid state-change classification; it was refused.")
    if not policy.requires_approval and skill_name not in NO_APPROVAL_ACTIONS:
        raise InvalidAction("This state-changing skill has no required approval policy; it was refused.")
    if not isinstance(params, dict) or set(params) != policy.parameter_names:
        raise InvalidAction("This skill received invalid parameters; it was refused.")
    if skill_name == "open_target":
        target = params["target"]
        if not isinstance(target, str) or target.casefold().strip() not in config.APPS and target.casefold().strip() not in config.WEBSITES:
            raise InvalidAction("The requested target is not on the approved app or website list.")
    elif skill_name in {"save_note", "search_notes", "chat", "research_web", "search_files", "add_task", "copy_to_clipboard", "get_weather"}:
        key = {
            "save_note": "text", "search_notes": "query", "chat": "message",
            "research_web": "query", "search_files": "query", "add_task": "text",
            "copy_to_clipboard": "text", "get_weather": "location",
        }[skill_name]
        value = params[key]
        if skill_name == "get_weather":
            if not isinstance(value, str) or len(value) > 100 or any(ord(char) < 32 for char in value):
                raise InvalidAction("The weather location must be valid text up to 100 characters.")
        else:
            if not isinstance(value, str) or not value.strip():
                raise InvalidAction(f"The {key} value must be nonempty text.")
            if skill_name in {"save_note", "add_task"} and len(value) > MAX_NOTE_LENGTH:
                raise InvalidAction("The text is longer than Iris's allowed limit.")
            if skill_name == "copy_to_clipboard" and len(value) > 5000:
                raise InvalidAction("The text is longer than Iris's allowed limit.")
            if skill_name == "chat" and len(value) > MAX_CHAT_LENGTH:
                raise InvalidAction("The chat message is longer than Iris's allowed limit.")
            if skill_name == "research_web" and (len(value.strip()) < 3 or len(value) > 500):
                raise InvalidAction("The research query must be 3 to 500 characters.")
            if skill_name == "search_files" and (
                len(value) > skills.MAX_FILE_SEARCH_QUERY_LENGTH or "/" in value or "\\" in value
                or value.strip() in {".", ".."} or any(ord(char) < 32 for char in value)
            ):
                raise InvalidAction("Use a plain filename or folder-name query of 1 to 120 characters.")
    elif skill_name in {"delete_note", "open_search_result", "complete_task", "delete_task"}:
        index = params["index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 1:
            raise InvalidAction("A selection number must be a positive integer.")
    elif skill_name == "set_timer":
        seconds = params["seconds"]
        message = params["message"]
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 1 or seconds > 86400:
            raise InvalidAction("Timer duration must be between 1 and 86400 seconds.")
        if not isinstance(message, str) or not message.strip() or len(message) > 500:
            raise InvalidAction("Timer message must be 1 to 500 characters.")
    elif skill_name in {"analyze_screen", "ui_click", "ui_type"}:
        frame_id = params["frame_id"]
        if not isinstance(frame_id, str) or not re.fullmatch(r"[a-f0-9]{64}", frame_id):
            raise InvalidAction("A valid current screen capture is required.")
        if skill_name == "analyze_screen":
            question = params["question"]
            if not isinstance(question, str) or not question.strip() or len(question) > 500:
                raise InvalidAction("The screen question must be 1 to 500 characters.")
        if skill_name in {"ui_click", "ui_type"}:
            for coordinate in (params["x"], params["y"]):
                if isinstance(coordinate, bool) or not isinstance(coordinate, int) or coordinate < 0:
                    raise InvalidAction("Screen coordinates must be nonnegative integers.")
        if skill_name == "ui_type":
            text = params["text"]
            if (not isinstance(text, str) or not text.strip() or len(text) > 500
                    or any(ord(character) < 32 for character in text)):
                raise InvalidAction("Typed text must be 1 to 500 characters without control characters.")
    elif skill_name == "create_skill_proposal":
        name, purpose = params["name"], params["purpose"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name):
            raise InvalidAction("The proposal name is invalid.")
        if not isinstance(purpose, str) or len(purpose.strip()) < 10 or len(purpose) > 500:
            raise InvalidAction("The proposal purpose must be 10 to 500 characters.")
    elif skill_name in {"approve_skill_proposal", "withdraw_skill_proposal"}:
        name, version = params["name"], params["version"]
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name)
                or isinstance(version, bool) or not isinstance(version, int) or version < 1):
            raise InvalidAction("The proposal name or version is invalid.")
    return policy


def validate_policy(skill_name, params):
    """Validate registry policy and parameter keys before a plan is accepted."""
    return _policy_for(skill_name, params)


def _snapshot_params(params):
    """Copy plain JSON parameters so caller mutation cannot alter approval."""
    def validate_value(value):
        if value is None or type(value) in {str, bool, int}:
            return
        if type(value) is float:
            if not math.isfinite(value):
                raise InvalidAction("Action parameters must contain finite JSON values.")
            return
        if type(value) is list:
            for item in value:
                validate_value(item)
            return
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise InvalidAction("Action parameter object keys must be text.")
            for item in value.values():
                validate_value(item)
            return
        raise InvalidAction("Action parameters must contain plain JSON values.")

    if type(params) is not dict:
        raise InvalidAction("Action parameters must be a plain object.")
    try:
        validate_value(params)
        return json.loads(json.dumps(params, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError, RecursionError, OverflowError) as error:
        raise InvalidAction("Action parameters could not be safely copied.") from error


def approve_reviewed_action(skill_name, params, details, input_fn=input):
    """Ask the gateway for approval after a skill has displayed exact contents."""
    _policy_for(skill_name, params)
    approval_context.require(skill_name, params)
    try:
        answer = input_fn(f"Iris is about to {details}. Type yes to approve this exact action: ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if not isinstance(answer, str) or answer.strip().casefold() != "yes":
        raise ApprovalDenied(f"Approval denied; {skill_name} was not run.")


def _approval_details(skill_name, params, prepared_target=None):
    """Describe the exact user-visible operation before asking for approval."""
    if skill_name == "open_target":
        return f"open the approved app or website {params['target']!r}"
    if skill_name == "save_note":
        return f"save this exact note: {params['text']!r}"
    if skill_name == "delete_note":
        return f"delete note number {params['index']}"
    if skill_name == "research_web":
        return f"send this research query to the configured provider: {params['query']!r}"
    if skill_name == "create_skill_proposal":
        return f"ask the configured AI to draft skill {params['name']!r} for {params['purpose']!r}"
    if skill_name == "approve_skill_proposal":
        return f"review proposal {params['name']} v{params['version']} (a second approval is required after its contents are shown)"
    if skill_name == "withdraw_skill_proposal":
        return f"review and withdraw proposal {params['name']} v{params['version']} (a second approval is required before recording)"
    if skill_name == "open_search_result":
        selected = skills.describe_search_result(params["index"])
        if selected is None:
            raise InvalidAction("That search result is no longer available or is outside the approved roots.")
        path, kind = selected
        return f"open this {kind}: {str(path)!r}"
    if skill_name == "capture_screen":
        return "capture the current screen into temporary memory only; the image will not be saved"
    if skill_name == "analyze_screen":
        import screen_vision
        unavailable = screen_vision.configuration_status()
        if unavailable:
            raise InvalidAction(unavailable)
        return (
            f"send screenshot {params['frame_id']} to Gemini for external vision analysis; "
            "the image will leave this computer, may contain private information, and may incur API usage charges. "
            f"Question: {params['question']!r}"
        )
    if skill_name in {"ui_click", "ui_type"}:
        if prepared_target is None:
            raise InvalidAction("The UI target could not be validated; it was refused.")
        if skill_name == "ui_click":
            return (
                f"take a fresh local screenshot and click {prepared_target.description!r} "
                f"at ({params['x']}, {params['y']}) if the screen and target remain unchanged"
            )
        return (
            f"take a fresh local screenshot and replace the text in {prepared_target.description!r} "
            f"at ({params['x']}, {params['y']}) with exactly {params['text']!r} "
            "if the screen and target remain unchanged"
        )
    if skill_name == "add_task":
        return f"save this task: {params['text']!r}"
    if skill_name == "complete_task":
        return f"mark task {params['index']} as completed"
    if skill_name == "delete_task":
        return f"delete task {params['index']}"
    if skill_name == "set_timer":
        return f"set a timer for {params['seconds']} seconds: {params['message']!r}"
    if skill_name == "copy_to_clipboard":
        return f"copy text to clipboard: {params['text']!r}"
    if skill_name == "run_trial_skill":
        return f"run trial skill {params['skill_id']!r} in the isolated sandbox"
    if skill_name == "promote_trial_skill":
        return f"promote trial skill {params['skill_id']!r} to permanent status"
    if skill_name == "delete_trial_skill":
        return f"delete trial skill {params['skill_id']!r} from the registry"
    raise InvalidAction("This skill has no approval description; it was refused.")


def _dispatch(skill_name, params, input_fn, prepared_target=None, prepared_screen_frame=None):
    """Call one fixed Python handler without interpreting user or AI text as code."""
    if skill_name == "open_target":
        return skills.open_approved(params["target"])
    if skill_name == "tell_time":
        return skills.tell_time()
    if skill_name == "tell_date":
        return skills.tell_date()
    if skill_name == "save_note":
        return skills.add_note(params["text"])
    if skill_name == "list_notes":
        return skills.show_notes()
    if skill_name == "search_notes":
        return skills.search_notes(params["query"])
    if skill_name == "delete_note":
        return skills.delete_note(params["index"], approved=True)
    if skill_name == "research_web":
        return skills.research_web(params["query"])
    if skill_name == "create_skill_proposal":
        return skill_development.create_proposal(params["name"], params["purpose"], input_fn)
    if skill_name == "approve_skill_proposal":
        return skill_development.approve_for_manual_integration(params["name"], params["version"], input_fn)
    if skill_name == "withdraw_skill_proposal":
        return skill_development.withdraw_proposal(params["name"], params["version"], input_fn)
    if skill_name == "chat":
        return ai.ask(params["message"])
    if skill_name == "help":
        return skills.help_text()
    if skill_name == "search_files":
        return skills.search_files(params["query"])
    if skill_name == "open_search_result":
        return skills.open_search_result(params["index"])
    if skill_name == "capture_screen":
        import screen_capture
        return screen_capture.capture_screen()
    if skill_name == "analyze_screen":
        import screen_vision
        return screen_vision.analyze_screen(
            params["frame_id"], params["question"], prepared_screen_frame
        )
    if skill_name == "ui_click":
        import ui_automation
        return ui_automation.click_target(params, prepared_target)
    if skill_name == "ui_type":
        import ui_automation
        return ui_automation.type_into_target(params, prepared_target)
    if skill_name == "add_task":
        return skills.add_task(params["text"])
    if skill_name == "list_tasks":
        return skills.list_tasks()
    if skill_name == "complete_task":
        return skills.complete_task(params["index"])
    if skill_name == "delete_task":
        return skills.delete_task(params["index"])
    if skill_name == "set_timer":
        return skills.set_timer(params["seconds"], params["message"])
    if skill_name == "list_timers":
        return skills.list_timers()
    if skill_name == "system_status":
        return skills.system_status()
    if skill_name == "battery_status":
        return skills.battery_status()
    if skill_name == "get_weather":
        return skills.get_weather(params["location"])
    if skill_name == "read_clipboard":
        return skills.read_clipboard()
    if skill_name == "copy_to_clipboard":
        return skills.copy_to_clipboard(params["text"])
    if skill_name == "list_trial_skills":
        import dynamic_skills
        return dynamic_skills.list_formatted()
    if skill_name == "run_trial_skill":
        import dynamic_skills
        res = dynamic_skills.execute_trial_skill(params["skill_id"])
        if res.success:
            return f"Trial skill succeeded:\n{res.output}" if res.output else "Trial skill executed successfully."
        return f"Trial skill failed: {res.error}"
    if skill_name == "promote_trial_skill":
        import dynamic_skills
        success, msg = dynamic_skills.promote_trial_skill(params["skill_id"])
        return msg
    if skill_name == "delete_trial_skill":
        import dynamic_skills
        success, msg = dynamic_skills.delete_trial_skill(params["skill_id"])
        return msg
    raise InvalidAction("Unregistered action; it was refused.")


def execute(skill_name, params, input_fn=input):
    """Validate policy and obtain immediate per-action approval before dispatch."""
    params = _snapshot_params(params)
    policy = _policy_for(skill_name, params)
    prepared_target = None
    prepared_screen_frame = None
    if skill_name in {"ui_click", "ui_type"}:
        import ui_automation
        try:
            prepared_target = ui_automation.prepare_target(skill_name, params)
        except RuntimeError as error:
            raise InvalidAction(str(error)) from error
    elif skill_name == "analyze_screen":
        import screen_capture
        prepared_screen_frame = screen_capture.latest_frame(params["frame_id"])
        if prepared_screen_frame is None:
            raise InvalidAction("That screenshot is no longer available; capture it again before analysis.")
    grant_params = params
    if skill_name == "open_search_result":
        selected = skills.describe_search_result(params["index"])
        if selected is None:
            raise InvalidAction("That search result is no longer available or is outside the approved roots.")
        path, kind = selected
        grant_params = {"index": params["index"], "path": str(path)}

    if policy.requires_approval:
        details = _approval_details(skill_name, params, prepared_target)
        try:
            answer = input_fn(f"Iris is about to {details}. Type yes to approve this action: ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if not isinstance(answer, str) or answer.strip().casefold() != "yes":
            raise ApprovalDenied(f"Approval denied; {skill_name} was not run.")

    grant = (
        approval_context._grant(
            skill_name, grant_params, capability=approval_context._GATEWAY_CAPABILITY
        )
        if policy.requires_approval else nullcontext()
    )
    with grant:
        return _dispatch(skill_name, params, input_fn, prepared_target, prepared_screen_frame)
