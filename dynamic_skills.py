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
