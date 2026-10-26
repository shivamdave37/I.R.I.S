"""Launch Jarvis and restore an approved update if startup fails."""

import json
import logging
import os
import re
import subprocess
import sys
import time

import config
from updater.policy import check_path


RESTART_CODE = 75
HEALTH_TIMEOUT_SECONDS = 30


def _local_path(name):
    """Return one fixed updater state path under the project data folder."""
    root = os.path.abspath(config.PROJECT_FOLDER)
    data = os.path.join(root, "data")
    if os.path.islink(root) or os.path.islink(data) or os.path.abspath(config.DATA_FOLDER) != data:
        raise ValueError("Updater state path is redirected.")
    return os.path.join(data, name)


def _pending_record():
    """Load and validate the pending restart record without following links."""
    path = _local_path("pending_update.json")
    if os.path.islink(path) or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as pending_file:
            record = json.load(pending_file)
        if not isinstance(record, dict):
            return None
        identifier = record.get("id")
        files = record.get("files")
        if not re.fullmatch(r"[a-f0-9]{12}", identifier or "") or not isinstance(files, list) or not files:
            return None
        if any(not isinstance(item, str) or check_path(item) != "tier1" for item in files):
            return None
        return record
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _restore_pending(record):
    """Restore exact backup bytes for every fixed TIER 1 target in the marker."""
    backup_root = _local_path(os.path.join("backups", record["id"]))
    backup_parent = _local_path("backups")
    if os.path.islink(backup_parent) or os.path.islink(backup_root):
        raise ValueError("The backup folder is redirected.")
    for relative_path in record["files"]:
        backup = os.path.join(backup_root, *relative_path.replace("\\", "/").split("/"))
        target = os.path.join(config.PROJECT_FOLDER, *relative_path.replace("\\", "/").split("/"))
        if (os.path.islink(backup) or os.path.islink(os.path.dirname(backup)) or os.path.islink(target)
                or not os.path.isfile(backup) or not os.path.isfile(target)):
            raise ValueError("A backup or target file is missing or redirected.")
        with open(backup, "rb") as backup_file:
            original = backup_file.read()
        with open(target, "wb") as target_file:
            target_file.write(original)
    pending = _local_path("pending_update.json")
    os.remove(pending)
    logging.error("updater id=%s automatic startup rollback completed", record["id"])


def _start_main():
    """Start main.py with a fixed interpreter command in the project folder."""
    return subprocess.Popen([sys.executable, "main.py"], cwd=config.PROJECT_FOLDER)


def _wait_for_health(process):
    """Wait at most thirty seconds for the new main process to report startup."""
    marker = _local_path("health.ok")
    if os.path.islink(marker):
        return False
    try:
        deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return False
            if os.path.isfile(marker) and not os.path.islink(marker):
                return True
            time.sleep(0.1)
        return False
    except OSError:
        return False


def run():
    """Monitor Jarvis restarts and roll back an update whose startup fails."""
    os.makedirs(os.path.join(config.PROJECT_FOLDER, "logs"), exist_ok=True)
    logging.basicConfig(filename=os.path.join(config.PROJECT_FOLDER, "logs", "jarvis.log"),
                        level=logging.INFO, format="%(asctime)s | %(message)s", encoding="utf-8")
    while True:
        record = _pending_record()
        pending_path = _local_path("pending_update.json")
        if os.path.lexists(pending_path) and record is None:
            logging.error("launcher refused an invalid pending update record")
            return 1
        marker = _local_path("health.ok")
        if os.path.islink(marker):
            return 1
        if os.path.isfile(marker):
            os.remove(marker)
        try:
            process = _start_main()
        except OSError as error:
            logging.error("launcher could not start main.py: %s", type(error).__name__)
            return 1
        if record is not None:
            if _wait_for_health(process):
                os.remove(_local_path("pending_update.json"))
                logging.info("updater id=%s startup health passed", record["id"])
            else:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    process.kill()
                    process.wait(timeout=5)
                try:
                    _restore_pending(record)
                except (OSError, ValueError) as error:
                    logging.exception("updater id=%s automatic rollback failed (%s)", record["id"], type(error).__name__)
                    return 1
                continue
        result = process.wait()
        if result == RESTART_CODE:
            continue
        return result


if __name__ == "__main__":
    raise SystemExit(run())
