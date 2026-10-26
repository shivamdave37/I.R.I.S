"""Apply only an unchanged, tested proposal after typed admin approval."""

import hashlib
import json
import logging
import os
import time

import config
from confirm import ask_choice
from iris.tasks import TaskState
from updater import patcher, proposal as proposal_store
from updater.policy import check_path


def _data_path(name):
    """Return a data path only when project data is not redirected."""
    root = os.path.abspath(config.PROJECT_FOLDER)
    data = os.path.join(root, "data")
    if os.path.abspath(config.DATA_FOLDER) != data or os.path.islink(root) or os.path.islink(data):
        raise ValueError("Updater data storage is redirected.")
    return os.path.join(data, name)


def _active_task_exists(supervisor):
    """Return whether any task is currently running."""
    return any(task.state == TaskState.RUNNING for task in supervisor.tasks.values())


def _base_files_match(proposal):
    """Check that every target still has the exact version used in the diff."""
    for relative_path, expected_hash in proposal.base_hashes.items():
        if check_path(relative_path) != "tier1":
            return False
        full_path = os.path.join(config.PROJECT_FOLDER, *relative_path.split("/"))
        if os.path.islink(full_path) or not os.path.isfile(full_path):
            return False
        with open(full_path, "rb") as original:
            if hashlib.sha256(original.read()).hexdigest() != expected_hash:
                return False
    return set(proposal.files) == set(proposal.base_hashes)


def _save_request(proposal, instruction):
    """Write the human-readable request without changing source code."""
    folder = _data_path("update_requests")
    if os.path.islink(folder):
        raise ValueError("The update request folder is redirected.")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, proposal.id + ".md")
    if os.path.islink(path):
        raise ValueError("The update request file is redirected.")
    text = (f"# Update request {proposal.id}\n\nReason: {proposal.reason}\n\n"
            f"Instruction: {instruction}\n\nTarget files: {', '.join(sorted(proposal.files))}\n")
    with open(path, "w", encoding="utf-8") as request_file:
        request_file.write(text)
    return path


def review_proposal(identifier, supervisor=None, revise_callback=None, ask=ask_choice):
    """Show one proposal and return approval bound to its exact content hash."""
    proposal = proposal_store.find_proposal(identifier)
    if proposal is None:
        return None, "I couldn't find that update proposal."
    if proposal.status != "READY" or not proposal.test_result.get("passed"):
        return None, "This proposal did not pass all checks and cannot be approved."
    if not _base_files_match(proposal):
        return None, "A target file changed after this proposal was prepared. Create a fresh proposal."
    if supervisor and _active_task_exists(supervisor):
        return None, "Wait until no Iris task is RUNNING before applying an update."
    print("Update reason: " + proposal.reason)
    print("Risk summary: " + json.dumps(proposal.risk_summary, indent=2, sort_keys=True))
    print("Test result: " + proposal.test_result.get("result", "No test result."))
    print("Full diff:\n" + proposal.diff)
    while True:
        choice = ask("1 approve and apply | 2 why | 3 deny | 4 other way | 5 revise", {"1", "2", "3", "4", "5"})
        if choice == "1":
            if not _base_files_match(proposal):
                return None, "A target changed while approval was pending; nothing was applied."
            return {"id": proposal.id, "hash": proposal.hash}, "Approved."
        if choice == "2":
            print("Reason: " + proposal.reason)
            print("Deterministic risk summary: " + json.dumps(proposal.risk_summary, indent=2, sort_keys=True))
            continue
        if choice == "3":
            proposal.status = "DENIED"
            proposal_store.save_proposal(proposal)
            logging.info("updater id=%s choice=deny", proposal.id)
            return None, "The proposal was denied; no files changed."
        if choice == "4":
            instruction = ask("Type a short instruction for Codex and Antigravity", set())
            if instruction is None:
                return None, "No request was written."
            # The free-text request is read from a typed-only confirmation prompt by the main loop.
            try:
                path = _save_request(proposal, instruction)
            except (OSError, ValueError) as error:
                return None, f"The request could not be saved ({type(error).__name__})."
            logging.info("updater id=%s choice=other_way", proposal.id)
            return None, "Wrote the human request to " + path
        if choice == "5":
            if revise_callback is None or proposal.revisions >= 3:
                return None, "Revisions are unavailable or the three-revision limit was reached."
            instruction = ask("Type the revised instruction", set())
            if instruction is None:
                return None, "No revision was prepared."
            return revise_callback(proposal, instruction)


def _write_pending(identifier, files):
    """Write the launcher's fixed pending-update record atomically."""
    path = _data_path("pending_update.json")
    temporary = path + ".tmp"
    if os.path.islink(path) or os.path.islink(temporary):
        raise ValueError("The pending update marker is redirected.")
    with open(temporary, "w", encoding="utf-8") as pending_file:
        json.dump({"id": identifier, "time": time.time(), "files": sorted(files)}, pending_file)
    os.replace(temporary, path)


def _restore_backup(identifier, files):
    """Restore exact original bytes from a proposal's project-local backup."""
    backup_root = _data_path(os.path.join("backups", identifier))
    backup_parent = _data_path("backups")
    if os.path.islink(backup_parent) or os.path.islink(backup_root):
        raise ValueError("A rollback backup folder is redirected.")
    for relative_path in files:
        if check_path(relative_path) != "tier1":
            raise ValueError("A rollback target is outside TIER 1.")
        backup = os.path.join(backup_root, *relative_path.split("/"))
        target = os.path.join(config.PROJECT_FOLDER, *relative_path.split("/"))
        if (os.path.islink(backup) or os.path.islink(os.path.dirname(backup))
                or os.path.islink(target) or not os.path.isfile(backup)):
            raise ValueError("A rollback backup or target is missing or redirected.")
        with open(backup, "rb") as backup_file:
            contents = backup_file.read()
        with open(target, "wb") as target_file:
            target_file.write(contents)


def apply_approved(approval, supervisor=None):
    """Backup, apply, and locally commit an approved proposal without pushing."""
    if not isinstance(approval, dict):
        return False, "No typed approval was supplied."
    proposal = proposal_store.find_proposal(approval.get("id"))
    if proposal is None or proposal.status != "READY" or approval.get("hash") != proposal.hash:
        return False, "The approval does not match a ready proposal."
    current_hash = patcher._candidate_hash(proposal.reason, proposal.requested_by, proposal.files,
                                           proposal.base_hashes, proposal.revisions)
    if current_hash != proposal.hash or not _base_files_match(proposal):
        return False, "The proposal or a target changed after approval; nothing was applied."
    if supervisor and _active_task_exists(supervisor):
        return False, "An Iris task is RUNNING; nothing was applied."
    identifier = proposal.id
    try:
        backup_root = _data_path(os.path.join("backups", identifier))
        if os.path.islink(os.path.dirname(backup_root)) or os.path.islink(backup_root):
            return False, "The backup folder is redirected; nothing was applied."
        os.makedirs(backup_root, exist_ok=True)
        for relative_path in sorted(proposal.files):
            if check_path(relative_path) != "tier1":
                raise ValueError("A target is outside TIER 1.")
            target = os.path.join(config.PROJECT_FOLDER, *relative_path.split("/"))
            backup = os.path.join(backup_root, *relative_path.split("/"))
            if os.path.islink(target) or not os.path.isfile(target):
                raise ValueError("A target is missing or redirected.")
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            with open(target, "rb") as original, open(backup, "wb") as saved:
                saved.write(original.read())
        for relative_path, contents in proposal.files.items():
            target = os.path.join(config.PROJECT_FOLDER, *relative_path.split("/"))
            with open(target, "w", encoding="utf-8", newline="") as updated:
                updated.write(contents)
        _write_pending(identifier, proposal.files)
        from skills.github_tools import commit_update
        committed, message = commit_update(sorted(proposal.files), identifier, proposal.reason)
        if not committed:
            raise RuntimeError(message)
        proposal.status = "APPLIED_PENDING_RESTART"
        try:
            proposal_store.save_proposal(proposal)
        except (OSError, ValueError):
            logging.exception("updater id=%s applied but proposal status could not be saved", identifier)
        logging.info("updater id=%s applied and committed locally", identifier)
    except Exception as error:
        try:
            _restore_backup(identifier, proposal.files)
            pending = _data_path("pending_update.json")
            if os.path.isfile(pending) and not os.path.islink(pending):
                os.remove(pending)
        except (OSError, ValueError):
            logging.exception("updater id=%s rollback after apply failure failed", identifier)
        return False, f"The update could not be applied ({type(error).__name__}); original files were restored when possible."
    return True, message


def rollback_last(ask=ask_choice):
    """Restore the most recent applied proposal after a typed confirmation."""
    proposals = [item for item in proposal_store.load_proposals() if item.status == "APPLIED_PENDING_RESTART"]
    if not proposals:
        return "There is no applied update available to roll back."
    backups = _data_path("backups")
    proposal = max(proposals, key=lambda item: os.path.getmtime(os.path.join(backups, item.id)))
    print("This restores the exact backup for update " + proposal.id + ".")
    if ask("Type yes to restore this update", {"yes"}) != "yes":
        return "Rollback cancelled; no files changed."
    try:
        _restore_backup(proposal.id, proposal.files)
        proposal.status = "ROLLED_BACK"
        proposal_store.save_proposal(proposal)
        pending = _data_path("pending_update.json")
        if os.path.isfile(pending) and not os.path.islink(pending):
            os.remove(pending)
        logging.info("updater id=%s rolled back", proposal.id)
        return "The exact original files were restored. Restart Jarvis to use them."
    except (OSError, ValueError) as error:
        return f"Rollback failed safely ({type(error).__name__})."
