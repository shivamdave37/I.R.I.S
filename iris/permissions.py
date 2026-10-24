"""Collect and persist per-resource permission choices from the admin."""

import json
import logging
import os
import threading
import time

import config
from iris.console import input_broker


SENSITIVE_RESOURCES = {"GIT_REPO", "SCREEN_FOCUS", "NOTES_FILE", "USER_CONFIG_FILE"}


class PermissionManager:
    """Coordinate one visible permission prompt at a time."""

    def __init__(self, data_folder=None, timeout=60):
        """Load saved grants and initialize the single pending prompt slot."""
        self.data_folder = data_folder or config.DATA_FOLDER
        self.path = os.path.join(self.data_folder, "permissions.json")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._session_grants = set()
        self._saved_grants = self._load()
        self._pending = None

    def _load(self):
        """Read persisted grants while treating missing or bad data as empty."""
        try:
            with open(self.path, "r", encoding="utf-8") as permission_file:
                loaded = json.load(permission_file)
            if isinstance(loaded, dict):
                valid = set()
                for key, value in loaded.items():
                    skill, separator, resource = key.partition(":")
                    if (separator and value == "always" and skill in config.ALLOWED_SKILLS
                            and resource in config.IRIS_RESOURCES and resource not in SENSITIVE_RESOURCES):
                        valid.add(key)
                return valid
        except (OSError, ValueError):
            pass
        return set()

    def request(self, task):
        """Wait for the main input loop to gather each resource choice."""
        resources = list(task.needed_resources)
        skill = task.plan[0] if task.plan else "chat"
        reasons = []
        ask_resources = []
        for resource in resources:
            if resource not in config.IRIS_RESOURCES:
                self._audit(task, f"unknown resource denied: {resource}")
                return False
            grant_key = f"{skill}:{resource}"
            if resource not in SENSITIVE_RESOURCES and (grant_key in self._saved_grants or grant_key in self._session_grants):
                print(f"Using saved permission: {resource}")
                self._audit(task, f"saved grant used: {resource}")
                continue
            reason = config.RESOURCE_REASONS.get((resource, skill))
            if reason is None:
                self._audit(task, f"missing fixed reason denied: {skill}:{resource}")
                return False
            reasons.append((resource, reason, grant_key))
            ask_resources.append(resource)
        if not ask_resources:
            return True
        prompt_text = f"Task {task.id}: {task.name} wants:\n"
        for index, (resource, reason, _) in enumerate(reasons, 1):
            policy = "typed yes required every time" if resource in SENSITIVE_RESOURCES else "once/session/always/deny"
            prompt_text += f"  [{index}] {resource} - {reason} ({policy})\n"
        prompt_text += "Type one choice per item in order, separated by commas (sensitive items: type yes or deny).\nPermission choices: "
        prompt = input_broker.create_request(prompt_text, kind="permission")
        with self._lock:
            self._pending = {"task": task, "items": reasons, "prompt_id": prompt["id"]}
        self._audit(task, "permission request shown: " + ", ".join(ask_resources))
        input_broker.enqueue(prompt)
        answer_text = input_broker.wait_for_answer(prompt, self.timeout)
        with self._lock:
            if self._pending and self._pending["prompt_id"] == prompt["id"]:
                self._pending = None
        if answer_text is None or task.cancel_event.is_set():
            self._audit(task, "permission timeout or no answer: denied")
            return False
        choices = [item.strip().lower() for item in answer_text.split(",")]
        if len(choices) != len(reasons):
            self._audit(task, "invalid permission response denied")
            return False
        choices = ["once" if resource in SENSITIVE_RESOURCES and choice == "yes" else choice
                   for (resource, _, _), choice in zip(reasons, choices)]
        for (resource, _, _), choice in zip(reasons, choices):
            self._audit(task, f"permission answer {resource}={choice}")
        if any(choice == "deny" for choice in choices):
            return False
        if any(resource in SENSITIVE_RESOURCES and choice != "once"
               for (resource, _, _), choice in zip(reasons, choices)):
            return False
        new_session_grants = set()
        new_saved_grants = set(self._saved_grants)
        for (resource, _, grant_key), choice in zip(reasons, choices):
            if choice == "session":
                new_session_grants.add(grant_key)
            elif choice == "always":
                new_saved_grants.add(grant_key)
        if new_saved_grants != self._saved_grants:
            try:
                self._save(new_saved_grants)
            except OSError:
                self._audit(task, "failed to persist grant")
                return False
        self._saved_grants = new_saved_grants
        self._session_grants.update(new_session_grants)
        return True

    def pending_prompt(self):
        """Return a prompt identifier and resource count when input is needed."""
        with self._lock:
            if self._pending is None:
                return None
            return self._pending["task"].id, len(self._pending["items"])

    def answer(self, task_id, text, typed=True):
        """Submit the admin's typed comma-separated choices for the active task."""
        with self._lock:
            pending = self._pending
            if pending is None or pending["task"].id != task_id or not typed:
                return False
            raw_choices = [item.strip().lower() for item in text.split(",")]
            if len(raw_choices) != len(pending["items"]):
                return False
            for (resource, _, _), choice in zip(pending["items"], raw_choices):
                if resource in SENSITIVE_RESOURCES and choice not in {"yes", "deny"}:
                    return False
                if resource not in SENSITIVE_RESOURCES and choice not in {"once", "session", "always", "deny"}:
                    return False
            prompt_id = pending["prompt_id"]
        input_broker.pending()
        return input_broker.answer(prompt_id, text, typed=typed)

    def grants(self):
        """Return the saved grant labels for the grants admin command."""
        return sorted(self._saved_grants) or []

    def revoke(self, resource):
        """Remove all saved grants for one known resource."""
        if resource not in config.IRIS_RESOURCES:
            return False
        matches = {grant for grant in self._saved_grants if grant.endswith(f":{resource}")}
        self._saved_grants.difference_update(matches)
        try:
            self._save()
        except OSError:
            self._saved_grants.update(matches)
            return False
        self._audit(None, f"grant revoked: {resource}")
        return bool(matches)

    def _save(self, grants=None):
        """Persist non-sensitive grants without writing outside the project data folder."""
        os.makedirs(self.data_folder, exist_ok=True)
        # A temporary file plus replace avoids partially written permission state.
        temporary_path = self.path + ".tmp"
        saved_grants = self._saved_grants if grants is None else grants
        with open(temporary_path, "w", encoding="utf-8") as permission_file:
            json.dump({grant: "always" for grant in sorted(saved_grants)}, permission_file, indent=2)
        os.replace(temporary_path, self.path)

    @staticmethod
    def _audit(task, event):
        """Record permission decisions with a timestamp and task identifier."""
        task_id = task.id if task else "admin"
        logging.info("task_id=%s | permission | %s | %s", task_id, time.strftime("%Y-%m-%d %H:%M:%S"), event)
