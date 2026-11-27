"""Isolated sandbox execution harness for trial and self-learned skills."""

from dataclasses import dataclass
import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

import config

SANDBOX_DIR = config.DATA_FOLDER / "sandbox_run"
DEFAULT_TIMEOUT_SECONDS = 5.0

BANNED_AST_NODES = (
    ast.Global,
    ast.Nonlocal,
)

BANNED_CALL_NAMES = frozenset({
    "eval", "exec", "__import__", "compile", "globals", "locals", "input"
})

BANNED_MODULE_NAMES = frozenset({
    "socket", "http.server", "ftplib", "smtplib", "telnetlib", "ctypes", "winreg"
})


@dataclass
class SandboxResult:
    """Outcome of running code in the isolated subprocess sandbox."""

    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    timed_out: bool = False


def validate_skill_source(source_code: str) -> Tuple[bool, str]:
    """Inspect Python syntax tree to guarantee the trial code adheres to security boundaries."""
    text = str(source_code or "").strip()
    if not text:
        return False, "Skill code cannot be empty."

    if any(secret_term in text for secret_term in ("GEMINI_API_KEY", "TAVILY_API_KEY", ".env")):
        return False, "Trial skill code cannot reference environment secrets or .env files."

    try:
        tree = ast.parse(text)
    except SyntaxError as err:
        return False, f"Syntax error in skill code: {err}"

    for node in ast.walk(tree):
        if isinstance(node, BANNED_AST_NODES):
            return False, f"Banned Python language feature: {type(node).__name__}"

        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in BANNED_MODULE_NAMES:
                    return False, f"Importing '{base}' is forbidden in sandbox."

        if isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module.split(".")[0]
                if base in BANNED_MODULE_NAMES:
                    return False, f"Importing from '{base}' is forbidden in sandbox."

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALL_NAMES:
                return False, f"Calling '{node.func.id}' is forbidden in sandbox."

    return True, "Code passed security validation."


def execute_in_sandbox(
    source_code: str,
    args: Optional[List[str]] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> SandboxResult:
    """Execute trial Python code in an isolated subprocess with stripped environment and strict timeout."""
    is_valid, reason = validate_skill_source(source_code)
    if not is_valid:
        return SandboxResult(success=False, output="", error=f"Security rejection: {reason}", exit_code=-1)

    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize environment: scrub all API keys, tokens, and credentials
    safe_env = {
        key: value for key, value in os.environ.items()
        if not any(token in key.upper() for token in ("KEY", "SECRET", "TOKEN", "AUTH", "PASS"))
    }
    safe_env["PYTHONPATH"] = str(config.PROJECT_FOLDER)

    fd, temp_file_path = tempfile.mkstemp(prefix="trial_", suffix=".py", dir=SANDBOX_DIR)
    os.close(fd)
    script_path = Path(temp_file_path)

    try:
        script_path.write_text(source_code, encoding="utf-8")
        cmd = [sys.executable, str(script_path)] + (args or [])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(SANDBOX_DIR),
            env=safe_env,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            exit_code = process.returncode
            success = (exit_code == 0)
            return SandboxResult(
                success=success,
                output=stdout.strip(),
                error=stderr.strip(),
                exit_code=exit_code,
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return SandboxResult(
                success=False,
                output="",
                error=f"Trial skill execution exceeded timeout limit ({timeout_seconds}s). Terminated.",
                exit_code=-2,
                timed_out=True,
            )
    except Exception as exc:
        return SandboxResult(success=False, output="", error=str(exc), exit_code=-3)
    finally:
        try:
            if script_path.exists():
                script_path.unlink()
        except OSError:
            pass
