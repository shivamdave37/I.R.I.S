"""Create inert, statically checked skill proposals for human review."""

import ast
from datetime import datetime, timezone
import json
import keyword
from pathlib import Path
import re

import ai
import config


PROPOSALS_FOLDER = config.PROJECT_FOLDER / "skill_proposals"
MAX_SOURCE_LENGTH = 12000
RESERVED_NAMES = {"open_target", "tell_time", "tell_date", "save_note", "list_notes", "search_notes", "delete_note", "research_web", "chat", "help"}
SAFE_BUILTINS = {"abs", "all", "any", "bool", "float", "int", "len", "max", "min", "round", "sorted", "str", "sum"}
ALLOWED_NODES = {
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Expr,
    ast.Constant, ast.Name, ast.Load, ast.Store, ast.Call, ast.keyword,
    ast.Assign, ast.If, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Subscript, ast.Slice,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
}


def validate_proposal(name, purpose, source):
    """Check proposal metadata and allow only a small, non-I/O Python subset."""
    _validate_metadata(name, purpose)
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_SOURCE_LENGTH:
        raise ValueError(f"Source must contain 1 to {MAX_SOURCE_LENGTH} characters.")
    if any(ord(char) < 32 and char not in "\n\t" for char in source):
        raise ValueError("Source contains unsupported control characters.")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ValueError(f"Python syntax check failed at line {error.lineno}.") from None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Source must contain exactly one top-level synchronous function.")
    function = tree.body[0]
    if function.name != f"skill_{name}" or function.decorator_list:
        raise ValueError(f"The only function must be named skill_{name} and have no decorators.")
    arguments = function.args
    if (
        [argument.arg for argument in arguments.args] != ["request"]
        or arguments.posonlyargs or arguments.kwonlyargs or arguments.vararg or arguments.kwarg
        or arguments.defaults or arguments.kw_defaults
    ):
        raise ValueError("The function must accept only one required argument named request.")
    docstring = ast.get_docstring(function, clean=False)
    if not docstring or "\n" in docstring:
        raise ValueError("The function needs a one-line docstring.")
    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES:
            raise ValueError(f"Disallowed Python syntax: {type(node).__name__}.")
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in {"open", "eval", "exec", "compile", "globals", "locals", "getattr", "setattr", "delattr", "input", "print"}):
            raise ValueError(f"Disallowed name: {node.id}.")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in SAFE_BUILTINS):
            raise ValueError("Only the fixed pure built-in functions may be called.")
    return "Static checks passed: metadata, one-function shape, syntax, and restricted AST."


def _validate_metadata(name, purpose):
    """Validate the proposed skill name and purpose before requesting code."""
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name):
        raise ValueError("Use a simple skill name: lowercase letters, digits, and underscores.")
    if keyword.iskeyword(name) or name in RESERVED_NAMES:
        raise ValueError("That skill name is reserved.")
    if not isinstance(purpose, str) or len(purpose.strip()) < 10 or len(purpose) > 500:
        raise ValueError("The purpose must be between 10 and 500 characters.")
    if any(ord(char) < 32 and char not in "\n\t" for char in purpose):
        raise ValueError("The purpose contains unsupported control characters.")


def _safe_folder():
    """Ensure proposal storage resolves inside the project and is not redirected."""
    try:
        project = config.PROJECT_FOLDER.resolve()
        resolved_folder = PROPOSALS_FOLDER.resolve()
        return (
            not PROPOSALS_FOLDER.is_symlink()
            and project in resolved_folder.parents
        )
    except (OSError, RuntimeError):
        return False


def _proposal_path(name, version):
    """Build a numbered proposal path after checking its components."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name) or isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("Invalid proposal name or version.")
    return PROPOSALS_FOLDER / f"{name}-v{version:03d}.json"


def _append_event(event):
    """Append an audit event without overwriting previous proposal history."""
    if not _safe_folder():
        return False
    try:
        PROPOSALS_FOLDER.mkdir(parents=True, exist_ok=True)
        event_path = PROPOSALS_FOLDER / "events.jsonl"
        if event_path.is_symlink():
            return False
        with event_path.open("a", encoding="utf-8") as event_file:
            event_file.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _next_version(name):
    """Choose a fresh version number without replacing older proposals."""
    if not _safe_folder():
        raise ValueError("Proposal storage is redirected outside the project.")
    if not PROPOSALS_FOLDER.exists():
        return 1
    matches = []
    for path in PROPOSALS_FOLDER.glob(f"{name}-v*.json"):
        match = re.fullmatch(rf"{re.escape(name)}-v(\d{{3}})\.json", path.name)
        if match:
            matches.append(int(match.group(1)))
    return max(matches, default=0) + 1


def _strip_code_fence(source):
    """Remove only one complete Markdown code fence from a model draft."""
    text = source.strip()
    match = re.fullmatch(r"```(?:python)?\s*\n(.*?)\n```", text, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else text


def create_proposal(name, purpose, input_fn=input):
    """Generate, validate, display, and optionally save an inert skill proposal."""
    try:
        # Validate human-supplied metadata before sending it to the configured AI.
        _validate_metadata(name, purpose)
        source = _strip_code_fence(ai.generate_skill_proposal(name, purpose))
        checks = validate_proposal(name, purpose, source)
    except (ValueError, RuntimeError) as error:
        return f"Proposal validation failed: {error}. Candidate was not saved or run."

    print("Untrusted skill proposal (not executed):")
    print(source)
    print(checks)
    print("Runtime tests: NOT RUN; this environment has no isolated sandbox for generated code.")
    try:
        answer = input_fn("Type yes to save this inert proposal for human review, or anything else to cancel: ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if not isinstance(answer, str) or answer.strip().casefold() != "yes":
        return "Proposal creation denied; nothing was saved."

    try:
        version = _next_version(name)
        proposal_path = _proposal_path(name, version)
        if not _safe_folder():
            return "Proposal validation failed: proposal storage is redirected. Candidate was not saved."
        PROPOSALS_FOLDER.mkdir(parents=True, exist_ok=True)
        record = {
            "name": name,
            "version": version,
            "purpose": purpose.strip(),
            "source": source,
            "static_checks": checks,
            "runtime_tests": "not run; no isolated sandbox is configured",
            "status": "awaiting human code review; not active",
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        with proposal_path.open("x", encoding="utf-8") as proposal_file:
            json.dump(record, proposal_file, ensure_ascii=False, indent=2)
            proposal_file.write("\n")
        if not _append_event({"event": "proposal_saved", "name": name, "version": version, "time": record["created_utc"]}):
            return "Proposal validation failed: audit log could not be written. The saved draft is not active."
    except (OSError, ValueError):
        return "Proposal validation failed: the draft could not be saved safely."
    return f"Saved inert skill proposal {name} v{version}. It is not active; review {proposal_path.name} before manual integration."


def read_proposal(name, version):
    """Read and revalidate one saved proposal without importing or executing it."""
    try:
        path = _proposal_path(name, version)
        if not _safe_folder() or path.is_symlink() or not path.is_file():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        checks = validate_proposal(record["name"], record["purpose"], record["source"])
        if record["name"] != name or record["version"] != version:
            return None
        record["static_checks"] = checks
        return record
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def approve_for_manual_integration(name, version, input_fn=input):
    """Record typed human review approval without dynamically activating code."""
    record = read_proposal(name, version)
    if record is None:
        return "Proposal validation failed: no valid saved proposal was found."
    print(f"Proposal {name} v{version}: {record['purpose']}")
    print(record["source"])
    print(record["static_checks"])
    print("Runtime tests remain NOT RUN; approval does not install or activate this code.")
    try:
        answer = input_fn("After reviewing this exact proposal, type yes to approve manual integration: ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if not isinstance(answer, str) or answer.strip().casefold() != "yes":
        return "Proposal approval denied; it remains inactive."
    event = {"event": "approved_for_manual_integration", "name": name, "version": version, "time": datetime.now(timezone.utc).isoformat()}
    if not _append_event(event):
        return "Proposal validation failed: approval could not be recorded."
    return f"Approval recorded for manual integration of {name} v{version}; it remains inactive in Iris."


def withdraw_proposal(name, version, input_fn=input):
    """Record an approved withdrawal while preserving the proposal for audit."""
    if read_proposal(name, version) is None:
        return "Proposal validation failed: no valid saved proposal was found."
    try:
        answer = input_fn(f"Type yes to withdraw {name} v{version}; its record will be retained: ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if not isinstance(answer, str) or answer.strip().casefold() != "yes":
        return "Proposal withdrawal denied; it remains unchanged."
    event = {"event": "proposal_withdrawn", "name": name, "version": version, "time": datetime.now(timezone.utc).isoformat()}
    if not _append_event(event):
        return "Proposal validation failed: withdrawal could not be recorded."
    return f"Withdrew {name} v{version}; its proposal record remains available for audit."
