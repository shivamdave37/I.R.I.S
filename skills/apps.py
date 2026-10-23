"""Approved Windows application opening skill."""

import os
import shutil
import subprocess

import config


def launch_app(app_path):
    """Start one configured application without using a shell."""
    # On Windows, os.startfile acts like double-clicking the executable without a shell.
    if hasattr(os, "startfile"):
        os.startfile(app_path)
    else:
        # Subprocess without shell=True is the safe alternative when startfile is unavailable.
        subprocess.Popen([app_path])


def is_placeholder(app_path):
    """Identify sample paths so they are not mistaken for installed apps."""
    # Placeholder strings alert the user to edit config.py before running.
    return "YOUR_USERNAME" in app_path or "PATH\\TO" in app_path


def open_app(name):
    """Open an app only when its name and path are approved in settings."""
    app_path = config.APPS.get(name)
    # Strictly refuse apps not configured in settings.
    if app_path is None:
        return f"I can't open {name}; it is not in the approved app list."
    # Prevent crashing on unedited example paths.
    if is_placeholder(app_path):
        return f"Please update the {name} path in config.py before opening it."

    # PATH-based commands such as notepad.exe need lookup because they are not file paths.
    available_path = shutil.which(app_path)
    if not available_path and not os.path.exists(app_path):
        return f"I couldn't find {name}. Please fix its path in config.py."

    try:
        # Launch using resolved path or configured path.
        launch_app(available_path or app_path)
        return f"Opening {name}."
    except Exception:
        # Never crash if Windows cannot launch the target file.
        return f"I couldn't open {name}. Please check its path in config.py."

