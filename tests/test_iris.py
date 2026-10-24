"""Offline tests for Iris tasks, resource locking, planning, and worker safety."""

import json
import threading
import time
import unittest
from unittest.mock import patch

from iris.agent_planner import plan
from iris.iris import Iris
from iris.resources import ResourceManager
from iris.tasks import Task, TaskState


class ResourceTests(unittest.TestCase):
    """Check that Iris reserves all task resources atomically."""

    def test_reserve_all_is_atomic_and_release_frees_everything(self):
        """A failed multi-resource reservation must leave no partial ownership."""
        manager = ResourceManager()
        first = Task(1, "first", "", needed_resources=["GIT_REPO"])
        second = Task(2, "second", "", needed_resources=["NOTES_FILE", "GIT_REPO"])
        self.assertTrue(manager.reserve_all(first))
        self.assertFalse(manager.reserve_all(second))
        self.assertEqual(manager.held_by(2), [])
        manager.release(first)
        self.assertTrue(manager.reserve_all(second))
        manager.release(second)
        self.assertEqual(manager.snapshot(), {})

    def test_unknown_resource_is_denied(self):
        """Unknown resources must never enter the reservation table."""
        manager = ResourceManager()
        task = Task(1, "bad", "", needed_resources=["UNKNOWN"])
        self.assertFalse(manager.reserve_all(task))


class PlannerTests(unittest.TestCase):
    """Check fixed fast paths and strict validation of AI plans."""

    def test_known_command_skips_ai(self):
        """Simple time commands use the fixed plan without an AI call."""
        with patch("iris.agent_planner.ask_ai", side_effect=AssertionError("AI called")):
            self.assertEqual(plan("what's the time")["steps"], ["timeinfo"])

    def test_ai_plan_with_unknown_skill_is_rejected_after_one_retry(self):
        """Untrusted AI plans cannot name skills outside the fixed allowlist."""
        bad = json.dumps({"steps": ["run_code"], "resources": [], "estimate_seconds": 1})
        with patch("iris.agent_planner.ask_ai", return_value=bad) as ask:
            with self.assertRaises(ValueError):
                plan("please explain the seasons")
        self.assertEqual(ask.call_count, 2)


class IrisTests(unittest.TestCase):
    """Check basic task lifecycle and error handling without external apps."""

    def test_worker_finishes_and_reports_status(self):
        """A known command runs in a worker and appears as completed."""
        supervisor = Iris()
        try:
            with patch("router.handle", return_value="done"):
                task = supervisor.submit("what's the time")
                self.assertEqual(supervisor.wait(task.id, 2).state, TaskState.DONE)
                self.assertIn("DONE", supervisor.status())
                self.assertEqual(task.result, "done")
        finally:
            supervisor.stop()

    def test_worker_crash_is_recorded_and_supervisor_continues(self):
        """An exception from a routed skill marks one task failed without killing Iris."""
        supervisor = Iris()
        try:
            with patch("router.handle", side_effect=[RuntimeError("boom"), "fine"]):
                failed = supervisor.submit("what's the time")
                self.assertEqual(supervisor.wait(failed.id, 2).state, TaskState.FAILED)
                next_task = supervisor.submit("what's the date")
                self.assertEqual(supervisor.wait(next_task.id, 2).state, TaskState.DONE)
        finally:
            supervisor.stop()

    def test_timeout_cancels_and_releases_resource(self):
        """The watchdog cancels an overdue task and frees its reservation."""
        supervisor = Iris(task_timeout=0.05)
        try:
            def block(command):
                """Hold a mocked skill long enough for the watchdog to catch it."""
                time.sleep(0.15)
                return "late"
            with patch("router.handle", side_effect=block):
                task = supervisor.submit("latest news")
                deadline = time.monotonic() + 1
                while task.state != TaskState.CANCELLED and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(task.state, TaskState.CANCELLED)
                self.assertEqual(supervisor.resources.held_by(task.id), [])
        finally:
            supervisor.stop()


if __name__ == "__main__":
    unittest.main()
