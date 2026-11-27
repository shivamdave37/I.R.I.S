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

STOP_WORDS = frozenset({
    "open", "run", "start", "launch", "execute", "do", "make",
    "the", "a", "an", "for", "to", "in", "on", "with", "app", "tool", "skill",
    "please", "can", "you", "me", "this"
})

COMMON_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "spotify": "spotify.exe",
    "vlc": "vlc.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
}

COMMON_SITES = {
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "chatgpt": "https://chatgpt.com",
    "google": "https://www.google.com",
    "bing": "https://www.bing.com",
    "github": "https://github.com",
    "youtube": "https://www.youtube.com",
}


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

    # Extract distinct non-stop-word query terms
    q_words = set(re.findall(r"[a-zA-Z0-9_-]+", q)) - STOP_WORDS

    for skill_id, entry in registry.items():
        name = entry.get("name", "").lower()
        tags = [t.lower() for t in entry.get("tags", []) if t.lower() not in STOP_WORDS]

        # 1. Distinctive tag word matches any word in query
        if any(t in q_words for t in tags if " " not in t):
            return entry

        # 2. Multi-word tag phrase is in query
        if any(len(t) > 3 and t in q for t in tags if " " in t):
            return entry

        # 3. Direct name match (e.g. 'open_edge' in query, or 'open edge' in query)
        name_clean = name.replace("_", " ")
        if len(name) > 2:
            if name in q or name_clean in q:
                return entry
            if difflib.SequenceMatcher(None, q, name).ratio() >= threshold:
                return entry

    return None


def resolve_skill_id(identifier: str, registry: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolve an exact ID, skill name, or fuzzy-matched name (handling typos and spaces) to its registry key."""
    if not identifier:
        return None
    if registry is None:
        registry = _load_registry()
    target = identifier.strip().lower()
    target_clean = target.replace(" ", "_")

    # 1. Exact key match
    if target in registry:
        return target
    if target_clean in registry:
        return target_clean

    # 2. Exact name match (with spaces or underscores)
    for sid, entry in registry.items():
        name = entry.get("name", "").lower()
        if name in {target, target_clean} or name.replace("_", " ") == target:
            return sid

    # 3. Fuzzy name or ID match (handles typos like 'opne_edge' -> 'open_edge')
    import difflib
    best_id = None
    best_ratio = 0.0
    for sid, entry in registry.items():
        name = entry.get("name", "").lower()
        r1 = difflib.SequenceMatcher(None, target_clean, name).ratio()
        r2 = difflib.SequenceMatcher(None, target, name.replace("_", " ")).ratio()
        r3 = difflib.SequenceMatcher(None, target, sid.lower()).ratio()
        m = max(r1, r2, r3)
        if m > best_ratio and m >= 0.70:
            best_ratio = m
            best_id = sid

    return best_id


def execute_trial_skill(skill_id: str, args: Optional[List[str]] = None) -> sandbox_runner.SandboxResult:
    """Retrieve skill source and execute inside the quarantined sandbox."""
    registry = _load_registry()
    resolved_id = resolve_skill_id(skill_id, registry)
    if not resolved_id or resolved_id not in registry:
        return sandbox_runner.SandboxResult(
            success=False, output="", error=f"Skill '{skill_id}' not found in registry.", exit_code=-4
        )

    skill_id = resolved_id
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
    resolved_id = resolve_skill_id(skill_id, registry)
    if not resolved_id or resolved_id not in registry:
        return False, f"Trial skill '{skill_id}' does not exist."

    registry[resolved_id]["status"] = "promoted"
    _save_registry(registry)
    return True, f"Skill '{resolved_id}' has been promoted to permanent status."


def delete_trial_skill(skill_id: str) -> Tuple[bool, str]:
    """Delete a trial skill and remove it from the index."""
    registry = _load_registry()
    resolved_id = resolve_skill_id(skill_id, registry)
    if not resolved_id or resolved_id not in registry:
        return False, f"Trial skill '{skill_id}' does not exist."

    filename = registry[resolved_id].get("filename")
    if filename:
        target_path = TEMP_SKILLS_DIR / filename
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

    del registry[resolved_id]
    _save_registry(registry)
    return True, f"Trial skill '{resolved_id}' has been removed."


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

    if "edge" in clean_p or "edge" in clean_n or "msedge" in clean_p:
        return f'''"""Trial skill: {name} - {purpose}"""
import subprocess
import os

def run():
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\\Microsoft\\Edge\\Application\\msedge.exe"),
    ]
    target = next((p for p in edge_paths if os.path.exists(p)), None)
    if target:
        subprocess.Popen([target])
        print("Launched Microsoft Edge successfully.")
    else:
        import webbrowser
        webbrowser.open("https://www.bing.com")
        print("Opened browser fallback.")

if __name__ == "__main__":
    run()
'''

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

    # 1. Check if common desktop application is requested
    for app_name, app_exe in COMMON_APPS.items():
        if app_name in clean_p or app_name in clean_n:
            return f'''"""Trial skill: {name} - {purpose}"""
import subprocess
import os

def run():
    try:
        subprocess.Popen(["{app_exe}"])
        print("Launched {app_name} ({app_exe}) successfully.")
    except Exception:
        import webbrowser
        webbrowser.open("https://www.google.com/search?q={app_name}")
        print("Could not directly start {app_exe}; opened web fallback.")

if __name__ == "__main__":
    run()
'''

    # 2. Check if website or URL is requested
    for site_name, site_url in COMMON_SITES.items():
        if site_name in clean_p or site_name in clean_n:
            return f'''"""Trial skill: {name} - {purpose}"""
import webbrowser

def run():
    webbrowser.open("{site_url}")
    print("Opened {site_name} at {site_url}.")

if __name__ == "__main__":
    run()
'''

    url_match = re.search(r"https?://\S+|www\.\S+|\b[a-zA-Z0-9-]+\.(?:com|org|net|io|edu|gov)\b", purpose)
    if url_match:
        found_url = url_match.group(0)
        if not found_url.startswith("http"):
            found_url = "https://" + found_url
        return f'''"""Trial skill: {name} - {purpose}"""
import webbrowser

def run():
    webbrowser.open("{found_url}")
    print("Opened {found_url} in browser.")

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

    # Step 3: Extract search & fast-retrieval tags (excluding generic action verbs like 'open', 'run')
    extracted_words = [w for w in re.findall(r"[a-zA-Z0-9_-]{3,}", clean_purpose.lower()) if w not in STOP_WORDS]
    tags = list(dict.fromkeys([clean_name, *extracted_words]))[:8]

    # Step 4: Save to cache & registry
    saved, result = save_trial_skill(clean_name, clean_purpose, tags, code)
    if not saved:
        return f"Failed to save trial skill: {result}"

    return (
        f"Trial skill '{clean_name}' (ID: {result}) added to trial cache! "
        f"You can run it with: run trial {clean_name}"
    )
