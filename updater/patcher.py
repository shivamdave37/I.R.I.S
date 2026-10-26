"""Validate full-file update proposals and report deterministic review evidence."""

import ast
import difflib
import hashlib
import json
import os
import re
import uuid

import config
from updater import proposal as proposal_store
from updater import sandbox_test
from updater.policy import check_path


_BANNED_PATTERNS = {
    "shell=True": re.compile(r"\bshell\s*=\s*True\b", re.IGNORECASE),
    "exec(": re.compile(r"\bexec\s*\("),
    "eval(": re.compile(r"\beval\s*\("),
    "__import__": re.compile(r"__import__"),
    "importlib": re.compile(r"\bimportlib\b"),
    "os.system": re.compile(r"\bos\s*\.\s*system\b"),
    "socket": re.compile(r"\bsocket\b", re.IGNORECASE),
    ".env reference": re.compile(r"\.env", re.IGNORECASE),
    "API_KEY reference": re.compile(r"API_KEY", re.IGNORECASE),
    "base64": re.compile(r"\bbase64\b", re.IGNORECASE),
}
_NETWORK_IMPORT = re.compile(r"\b(?:import|from)\s+(?:requests|urllib|httpx|aiohttp|ftplib)\b", re.IGNORECASE)
_SUBPROCESS_USE = re.compile(r"\b(?:import\s+subprocess|from\s+subprocess|subprocess\s*\.)\b")
_WRITE_OPEN = re.compile(r"\bopen\s*\([^\n)]*,\s*(?:mode\s*=\s*)?(['\"])[^'\"]*[wax+][^'\"]*\1", re.IGNORECASE)
_NETWORK_CALL_NAMES = {"urlopen", "urlretrieve", "get", "post", "put", "patch", "delete", "request", "create_connection"}


def _read_original(relative_path):
    """Read one allowed live file as UTF-8 text without following a link."""
    full_path = os.path.join(config.PROJECT_FOLDER, *relative_path.split("/"))
    if os.path.islink(full_path) or not os.path.isfile(full_path):
        raise ValueError("The target file is missing or redirected.")
    with open(full_path, "r", encoding="utf-8", newline="") as source_file:
        return source_file.read()


def _added_lines(old_text, new_text):
    """Return only inserted or replacement lines so existing safe code is not rescanned."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    added = []
    for tag, _, _, new_start, new_end in difflib.SequenceMatcher(None, old_lines, new_lines).get_opcodes():
        if tag in {"insert", "replace"}:
            added.extend(new_lines[new_start:new_end])
    return added


def _write_open_count(tree):
    """Count built-in open calls whose literal mode can write a file."""
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "open":
            continue
        mode = node.args[1] if len(node.args) > 1 else None
        for keyword in node.keywords:
            if keyword.arg == "mode":
                mode = keyword.value
        try:
            value = ast.literal_eval(mode) if mode is not None else "r"
        except (ValueError, TypeError):
            value = "unknown"
        if not isinstance(value, str) or any(flag in value.lower() for flag in "wax+"):
            count += 1
    return count


def _network_calls(tree):
    """Describe obvious standard network call forms in one parsed file."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        if name in _NETWORK_CALL_NAMES:
            found.append((name, ast.dump(node, include_attributes=False)))
    return found


def _function_map(tree):
    """Map function names to their syntax trees for a deterministic change list."""
    return {node.name: ast.dump(node, include_attributes=False)
            for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _check_protected_lines(old_text, new_text):
    """Require every protected line to remain byte-for-byte at its original line number."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    markers = [(index, line) for index, line in enumerate(old_lines) if "# PROTECTED" in line]
    return all(index < len(new_lines) and new_lines[index] == line for index, line in markers), len(markers)


def _scan_file(relative_path, old_text, new_text, old_tree, new_tree):
    """Return one file's line counts, changed functions, and every safety scan result."""
    added = _added_lines(old_text, new_text)
    added_text = "\n".join(added)
    checks = []
    for label, pattern in _BANNED_PATTERNS.items():
        passed = not pattern.search(added_text)
        checks.append({"rule": label, "passed": passed})
    checks.append({"rule": "new subprocess use", "passed": not _SUBPROCESS_USE.search(added_text)})
    checks.append({"rule": "new network import", "passed": not _NETWORK_IMPORT.search(added_text)})
    old_writes = _write_open_count(old_tree)
    new_writes = _write_open_count(new_tree)
    checks.append({"rule": "open() write mode", "passed": new_writes <= old_writes})
    old_network = _network_calls(old_tree)
    new_network = _network_calls(new_tree)
    checks.append({"rule": "new network call", "passed": len(new_network) <= len(old_network)})
    protected_ok, marker_count = _check_protected_lines(old_text, new_text)
    checks.append({"rule": "# PROTECTED lines unchanged", "passed": protected_ok, "markers": marker_count})
    old_functions = _function_map(old_tree)
    new_functions = _function_map(new_tree)
    changed_functions = sorted(name for name in set(old_functions) | set(new_functions)
                               if old_functions.get(name) != new_functions.get(name))
    diff_lines = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines()))
    added_count = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed_count = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    return {"path": relative_path, "lines_added": added_count, "lines_removed": removed_count,
            "functions_changed": changed_functions, "scans": checks}


def _candidate_hash(reason, requested_by, files, base_hashes, revisions):
    """Bind the exact full files, original hashes, reason, author role, and revision."""
    canonical = json.dumps({"reason": reason, "requested_by": requested_by, "files": files,
                            "base_hashes": base_hashes, "revisions": revisions},
                           sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_proposal(files, reason, requested_by="admin", revisions=0, run_tests=True):
    """Check a full-file patch, test it in a project copy, and save its review record."""
    identifier = uuid.uuid4().hex[:12]
    accepted_files = {}
    base_hashes = {}
    file_summaries = []
    diff_parts = []
    refusal = None
    if requested_by not in {"admin", "iris"} or not isinstance(reason, str) or not reason.strip():
        refusal = "A proposal needs a valid requester and a short reason."
    elif not isinstance(files, dict) or not 1 <= len(files) <= 3:
        refusal = "A proposal must change between one and three existing files."
    elif revisions < 0 or revisions > 3:
        refusal = "A proposal cannot have more than three revisions."
    else:
        for raw_path, new_text in files.items():
            relative_path = raw_path.replace("\\", "/") if isinstance(raw_path, str) else ""
            if check_path(relative_path) != "tier1":
                refusal = f"Refused non-TIER 1 path: {relative_path or '[invalid]'}."
                break
            if not isinstance(new_text, str):
                refusal = f"The new full file text is invalid: {relative_path}."
                break
            try:
                old_text = _read_original(relative_path)
                old_tree = ast.parse(old_text, filename=relative_path)
                new_tree = ast.parse(new_text, filename=relative_path)
            except SyntaxError as error:
                refusal = f"Syntax error in {relative_path} at line {error.lineno}."
                break
            except (OSError, UnicodeError, ValueError) as error:
                refusal = f"Could not safely read {relative_path} ({type(error).__name__})."
                break
            accepted_files[relative_path] = new_text
            base_hashes[relative_path] = hashlib.sha256(old_text.encode("utf-8")).hexdigest()
            summary = _scan_file(relative_path, old_text, new_text, old_tree, new_tree)
            file_summaries.append(summary)
            diff_parts.extend(difflib.unified_diff(old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                                                   fromfile="a/" + relative_path, tofile="b/" + relative_path))
            failed_checks = [check["rule"] for check in summary["scans"] if not check["passed"]]
            if failed_checks:
                refusal = f"Refused {relative_path}; failed scans: {', '.join(failed_checks)}."
                break
    diff_text = "".join(diff_parts)
    changed_lines = sum(item["lines_added"] + item["lines_removed"] for item in file_summaries)
    if refusal is None and changed_lines > 80:
        refusal = "A proposal may change no more than 80 lines."
    risk = {"files": file_summaries, "lines_added": sum(item["lines_added"] for item in file_summaries),
            "lines_removed": sum(item["lines_removed"] for item in file_summaries), "test_result": "not run"}
    candidate_hash = _candidate_hash(reason, requested_by, accepted_files, base_hashes, revisions)
    result = {"passed": False, "result": refusal or "The candidate was not tested."}
    status = "REFUSED" if refusal else "READY"
    if refusal is None and run_tests:
        result = sandbox_test.run_tests(accepted_files)
        status = "READY" if result.get("passed") else "TEST_FAILED"
    risk["test_result"] = result.get("result", "No test result.")
    proposal = proposal_store.Proposal(
        id=identifier, reason=reason, requested_by=requested_by, files=accepted_files, diff=diff_text,
        status=status, hash=candidate_hash, revisions=revisions, base_hashes=base_hashes,
        risk_summary=risk, test_result=result,
    )
    if status != "REFUSED":
        proposal_store.save_proposal(proposal)
    return proposal
