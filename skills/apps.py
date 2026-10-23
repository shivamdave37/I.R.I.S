"""Approved Windows application opening skill."""

import os
import shutil
import subprocess

import config


def launch_app(app_path):
    """Start one configured application without using a shell."""
    if hasattr(os, "startfile"):
        os.startfile(app_path)
    else:
        subprocess.Popen([app_path])


def is_placeholder(app_path):
    """Identify sample paths so they are not mistaken for installed apps."""
    return "YOUR_USERNAME" in app_path or "PATH\\TO" in app_path


def open_app(name):
    """Open an app only when its name and path are approved in settings."""
    app_path = config.APPS.get(name)
    if app_path is None:
        return f"I can't open {name}; it is not in the approved app list."
    if is_placeholder(app_path):
        return f"Please update the {name} path in config.py before opening it."

    # PATH-based commands such as notepad.exe need lookup because they are not file paths.
    available_path = shutil.which(app_path)
    if not available_path and not os.path.exists(app_path):
        return f"I couldn't find {name}. Please fix its path in config.py."

    try:
        launch_app(available_path or app_path)
        return f"Opening {name}."
    except Exception:
        return f"I couldn't open {name}. Please check its path in config.py."
