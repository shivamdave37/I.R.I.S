"""Reserve task resources together to prevent hold-and-wait deadlocks."""

import threading


KNOWN_RESOURCES = {"MIC_SPEAKER", "CLIPBOARD", "SCREEN_FOCUS", "GIT_REPO", "API_QUOTA", "NOTES_FILE", "USER_CONFIG_FILE", "LEARNED_SKILLS"}


class ResourceManager:
    """Track resource ownership with an atomic all-at-once reservation."""

    def __init__(self):
        """Create an empty ownership table guarded by one lock."""
        self._lock = threading.Lock()
        self._owners = {}

    def reserve_all(self, task):
        """Reserve every known free resource, or reserve none of them."""
        resources = sorted(set(task.needed_resources))
        if any(resource not in KNOWN_RESOURCES for resource in resources):
            return False
        # One lock covers both the availability check and every assignment.
        with self._lock:
            if any(resource in self._owners and self._owners[resource] != task.id for resource in resources):
                return False
            for resource in resources:
                self._owners[resource] = task.id
            return True

    def release(self, task):
        """Free every resource owned by this task."""
        with self._lock:
            for resource in list(self._owners):
                if self._owners[resource] == task.id:
                    del self._owners[resource]

    def held_by(self, task_id):
        """Return the resource names currently held by one task."""
        with self._lock:
            return sorted(resource for resource, owner in self._owners.items() if owner == task_id)

    def snapshot(self):
        """Return a safe copy of current resource ownership."""
        with self._lock:
            return dict(self._owners)
