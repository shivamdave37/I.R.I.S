"""Test candidate updates in an ignored project copy without touching live code."""

import os
import shutil
import subprocess
import sys
import tempfile

import config
from updater.policy import check_path


_EXCLUDED = {".env", "venv", ".git", "data", "logs", "models", "__pycache__", "proposed_skills"}


def _ignore_names(folder, names):
    """Return only known local or secret folders to omit from the sandbox copy."""
    return [name for name in names if name in _EXCLUDED or name.startswith("tmp")]


def run_tests(files, timeout=120):
    """Copy the project, apply candidate full files there, and run the fixed suite."""
    if not isinstance(files, dict) or not files:
        return {"passed": False, "result": "No candidate files were supplied."}
    if timeout != 120:
        return {"passed": False, "result": "The isolated test timeout is fixed at 120 seconds."}
    project_root = os.path.abspath(config.PROJECT_FOLDER)
    for relative_path, contents in files.items():
        if check_path(relative_path) != "tier1" or not isinstance(contents, str):
            return {"passed": False, "result": "A candidate path or file value was refused."}
        live_target = os.path.join(project_root, *relative_path.replace("\\", "/").split("/"))
        if os.path.islink(live_target) or not os.path.isfile(live_target):
            return {"passed": False, "result": "A candidate target is missing or redirected."}
    data_folder = os.path.join(project_root, "data")
    sandbox_parent = os.path.join(data_folder, "update_sandboxes")
    if os.path.islink(project_root) or os.path.islink(data_folder) or os.path.islink(sandbox_parent):
        return {"passed": False, "result": "The project or sandbox folder is redirected."}
    os.makedirs(sandbox_parent, exist_ok=True)
    temporary_root = tempfile.mkdtemp(prefix="test_", dir=sandbox_parent)
    sandbox_project = os.path.join(temporary_root, "project")
    try:
        shutil.copytree(project_root, sandbox_project, ignore=_ignore_names)
        for relative_path, contents in files.items():
            target = os.path.join(sandbox_project, *relative_path.replace("\\", "/").split("/"))
            if os.path.islink(target) or not os.path.isfile(target):
                return {"passed": False, "result": "A candidate target is missing or redirected."}
            with open(target, "w", encoding="utf-8", newline="") as candidate_file:
                candidate_file.write(contents)
        command = [sys.executable, "-m", "unittest", "discover", "tests"]
        result = subprocess.run(command, cwd=sandbox_project, capture_output=True, text=True,
                                timeout=timeout, check=False)
        if result.returncode == 0:
            return {"passed": True, "result": "All tests passed in the isolated project copy."}
        return {"passed": False, "result": f"The isolated test suite failed (exit code {result.returncode})."}
    except subprocess.TimeoutExpired:
        return {"passed": False, "result": f"The isolated test suite exceeded {timeout} seconds and was stopped."}
    except (OSError, ValueError) as error:
        return {"passed": False, "result": f"The isolated test could not run ({type(error).__name__})."}
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
