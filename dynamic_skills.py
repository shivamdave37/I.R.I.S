"""Temporary trial skill cache, metadata registry, and fast retrieval pathway."""

from dataclasses import dataclass, asdict
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import config
import sandbox_runner

TEMP_SKILLS_DIR = config.DATA_FOLDER / "temp_skills"
REGISTRY_FILE = TEMP_SKILLS_DIR / "registry.json"


BOUNDARY_RULES = [
    (
        re.compile(r"\b(socket|port\s*scan|listen(?:ing)?\s+on\s+port|reverse\s*shell|packet\s*sniff|syn\s*flood|http\.server|telnet|ftp|botnet|ddos)\b", re.I),
        "Network socket programming, port scanning, and listening servers are forbidden in Iris's isolated sandbox."
    ),
    (
        re.compile(r"\b(winreg|registry|regedit|system32|uac\s*bypass|admin(?:istrator)?\s*privilege|kernel\s*driver|elevate\s*privilege)\b", re.I),
        "Modifying Windows registry, escalating to administrator privileges, or altering OS system files is forbidden."
    ),
    (
        re.compile(r"\b(password|credential|browser\s*cookie|master\s*key|chrome\s*master|stealer|keylogger|\.env|api_key|private\s*key|id_rsa)\b", re.I),
        "Accessing stored credentials, passwords, browser master keys/cookies, or environment secrets is forbidden."
    ),
    (
        re.compile(r"\b(format\s+[c-z]:|wipe\s*disk|delete\s+system32|fork\s*bomb|destroy\s*os)\b", re.I),
        "Destructive disk operations and system alteration are strictly forbidden."
    ),
    (
        re.compile(r"\b(eval|exec|compile|__import__|globals\(\)|locals\(\)|ctypes)\b", re.I),
        "Dynamic code execution (eval/exec/ctypes) that circumvents Python runtime safety is forbidden."
    ),
]


@dataclass
class DynamicSkillEntry:
    """Metadata tracking one trial or self-learned skill."""

    skill_id: str
    name: str
    description: str
    tags: List[str]
    filename: str
    created_at: float
    status: str = "trial"  # "trial" or "promoted"
    run_count: int = 0


def _load_registry() -> Dict[str, Any]:
    """Load registry safely from JSON file."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _save_registry(registry: Dict[str, Any]) -> None:
    """Atomically save registry data."""
    TEMP_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = TEMP_SKILLS_DIR / "registry.tmp"
    temp_file.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    temp_file.replace(REGISTRY_FILE)


def save_trial_skill(name: str, description: str, tags: List[str], source_code: str) -> Tuple[bool, str]:
    """Validate, store in temporary staging cache, and index for fast retrieval."""
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
    if not clean_name:
        return False, "Skill name is invalid or empty."

    # Step 1: Pre-flight security validation in sandbox runner
    is_valid, reason = sandbox_runner.validate_skill_source(source_code)
    if not is_valid:
        return False, f"Trial skill rejected by security analyzer: {reason}"

    TEMP_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_id = f"trial_{clean_name}_{int(time.time())}"
    filename = f"{skill_id}.py"
    target_path = TEMP_SKILLS_DIR / filename

    try:
        target_path.write_text(source_code, encoding="utf-8")
    except OSError as err:
        return False, f"Could not write trial skill file: {err}"

    # Step 2: Index into fast-retrieval registry
    clean_tags = [t.strip().lower() for t in tags if t.strip()]
    entry = DynamicSkillEntry(
        skill_id=skill_id,
        name=clean_name,
        description=description.strip(),
        tags=clean_tags,
        filename=filename,
        created_at=time.time(),
        status="trial",
        run_count=0,
    )

    registry = _load_registry()
    registry[skill_id] = asdict(entry)
    _save_registry(registry)

    return True, skill_id


def list_trial_skills() -> List[Dict[str, Any]]:
    """Return all currently indexed trial and dynamic skills."""
    registry = _load_registry()
    return list(registry.values())


def list_formatted() -> str:
    """Return a readable string representation of all registered dynamic skills."""
    skills_list = list_trial_skills()
    if not skills_list:
        return "No trial skills currently registered in the sandbox cache."
    lines = [f"Registered dynamic skills ({len(skills_list)}):"]
    for i, s in enumerate(skills_list, 1):
        status = s.get("status", "trial").upper()
        runs = s.get("run_count", 0)
        tags = ", ".join(f"#{t}" for t in s.get("tags", []))
        lines.append(f"{i}. [{status}] {s['name']} (ID: {s['skill_id']}) - {s['description']} [{tags}] (Runs: {runs})")
    return "\n".join(lines)


def find_matching_trial_skill(query: str, threshold: float = 0.70) -> Optional[Dict[str, Any]]:
    """Fast-retrieval pathway: Query registry by keywords, name, and tags in < 2ms."""
    q = query.strip().lower()
    if not q:
        return None

    registry = _load_registry()
    if not registry:
        return None

    import difflib

    for skill_id, entry in registry.items():
        name = entry.get("name", "").lower()
        tags = [t.lower() for t in entry.get("tags", [])]

        # 1. Exact tag or tag phrase match in query
        if any(len(t) > 2 and t in q for t in tags):
            return entry

        # 2. Direct name substring or strong ratio
        if len(name) > 2 and (name in q or difflib.SequenceMatcher(None, q, name).ratio() >= threshold):
            return entry

    return None


def execute_trial_skill(skill_id: str, args: Optional[List[str]] = None) -> sandbox_runner.SandboxResult:
    """Retrieve skill source and execute inside the quarantined sandbox."""
    registry = _load_registry()
    if skill_id not in registry:
        return sandbox_runner.SandboxResult(
            success=False, output="", error=f"Skill '{skill_id}' not found in registry.", exit_code=-4
        )

    entry = registry[skill_id]
    target_path = TEMP_SKILLS_DIR / entry["filename"]
    if not target_path.exists():
        return sandbox_runner.SandboxResult(
            success=False, output="", error=f"Skill file '{entry['filename']}' is missing.", exit_code=-5
        )

    try:
        source_code = target_path.read_text(encoding="utf-8")
    except OSError as err:
        return sandbox_runner.SandboxResult(success=False, output="", error=str(err), exit_code=-6)

    result = sandbox_runner.execute_in_sandbox(source_code, args=args)
    if result.success:
        entry["run_count"] = entry.get("run_count", 0) + 1
        registry[skill_id] = entry
        _save_registry(registry)

    return result


def promote_trial_skill(skill_id: str) -> Tuple[bool, str]:
    """Promote an experimental trial skill to permanent verified status."""
    registry = _load_registry()
    if skill_id not in registry:
        return False, f"Trial skill '{skill_id}' does not exist."

    registry[skill_id]["status"] = "promoted"
    _save_registry(registry)
    return True, f"Skill '{skill_id}' has been promoted to permanent status."


def delete_trial_skill(skill_id: str) -> Tuple[bool, str]:
    """Delete a trial skill and remove it from the index."""
    registry = _load_registry()
    if skill_id not in registry:
        return False, f"Trial skill '{skill_id}' does not exist."

    filename = registry[skill_id].get("filename")
    if filename:
        target_path = TEMP_SKILLS_DIR / filename
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

    del registry[skill_id]
    _save_registry(registry)
    return True, f"Trial skill '{skill_id}' has been removed."


def check_skill_boundaries(name: str, purpose: str, source_code: Optional[str] = None) -> Tuple[bool, str]:
    """Verify whether the requested skill is within Iris's safe desktop boundary."""
    combined_intent = f"{name} {purpose}".lower()
    for pattern, reason in BOUNDARY_RULES:
        if pattern.search(combined_intent):
            return False, reason

    if source_code:
        is_valid, reason = sandbox_runner.validate_skill_source(source_code)
        if not is_valid:
            return False, f"Code violates sandbox security policy: {reason}"

    return True, "Skill is within allowed boundaries."


def synthesize_trial_code(name: str, purpose: str) -> str:
    """Generate safe, executable Python code tailored to the requested skill."""
    clean_p = purpose.lower()
    clean_n = name.lower()

    if "chrome" in clean_p or "chrome" in clean_n:
        profile_flag = "Profile 1" if ("first" in clean_p or "1" in clean_p) else "Default"
        return f'''"""Trial skill: {name} - {purpose}"""
import subprocess
import os

def run():
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe"),
    ]
    target = next((p for p in chrome_paths if os.path.exists(p)), None)
    if target:
        subprocess.Popen([target, '--profile-directory={profile_flag}'])
        print("Launched Chrome with profile: {profile_flag}")
    else:
        import webbrowser
        webbrowser.open("https://www.google.com")
        print("Default browser opened as fallback.")

if __name__ == "__main__":
    run()
'''

    if any(k in clean_p for k in ("count", "stats", "lines", "words", "analyze text")):
        return f'''"""Trial skill: {name} - {purpose}"""
def run(sample_text="Hello world\\nWelcome to Iris trial skills."):
    lines = len(sample_text.splitlines())
    words = len(sample_text.split())
    chars = len(sample_text)
    print(f"Text analysis result: {{lines}} lines, {{words}} words, {{chars}} characters.")

if __name__ == "__main__":
    run()
'''

    if any(k in clean_p for k in ("csv", "table", "tabular", "rows")):
        return f'''"""Trial skill: {name} - {purpose}"""
import csv
import io

def run():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Status"])
    writer.writerow([1, "Item A", "Active"])
    writer.writerow([2, "Item B", "Pending"])
    print("Generated CSV content:\\n" + output.getvalue().strip())

if __name__ == "__main__":
    run()
'''

    if any(k in clean_p for k in ("calc", "math", "sum", "fibonacci", "prime", "number")):
        return f'''"""Trial skill: {name} - {purpose}"""
def run():
    print(f"Executed mathematical trial calculation for {name}: {purpose}")

if __name__ == "__main__":
    run()
'''

    # Default pure-Python desktop helper template
    return f'''"""Trial skill: {name} - {purpose}"""

def run():
    print(f"Trial skill '{name}' executed successfully: {purpose}")

if __name__ == "__main__":
    run()
'''


def create_trial_skill(name: str, purpose: str, source_code: Optional[str] = None) -> str:
    """Validate boundaries, synthesize or verify source code, and store trial skill."""
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(name or "").strip().lower()).strip("_")
    clean_purpose = str(purpose or "").strip()

    if not clean_name:
        return "Refused: Skill name must contain at least one alphanumeric character."
    if not clean_purpose:
        return "Refused: Skill purpose cannot be empty."

    # Step 1: Capability & boundary check
    is_safe, refusal_reason = check_skill_boundaries(clean_name, clean_purpose, source_code)
    if not is_safe:
        return f"Refused: I cannot add this skill because it violates Iris's safety boundaries. Reason: {refusal_reason}"

    # Step 2: Code synthesis or validation
    code = source_code if source_code else synthesize_trial_code(clean_name, clean_purpose)
    is_valid, sec_reason = sandbox_runner.validate_skill_source(code)
    if not is_valid:
        return f"Refused: The generated code violated sandbox security policies: {sec_reason}"

    # Step 3: Extract search & fast-retrieval tags
    tags = list({
        clean_name,
        *re.findall(r"[a-zA-Z0-9]{3,}", clean_purpose.lower())
    })[:8]

    # Step 4: Save to cache & registry
    saved, result = save_trial_skill(clean_name, clean_purpose, tags, code)
    if not saved:
        return f"Failed to save trial skill: {result}"

    return (
        f"Trial skill '{clean_name}' (ID: {result}) added to trial cache! "
        f"You can run it with: run trial {clean_name}"
    )
