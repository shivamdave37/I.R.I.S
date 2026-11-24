"""Tests for new Iris capabilities: Tasks, Timers, System Health, Weather, and Clipboard."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import action_gateway
import config
import skills
import task_planner


class TaskSkillsTests(unittest.TestCase):
    """Ensure tasks are safely saved, listed, completed, and deleted under gateway governance."""

    def test_task_lifecycle_under_gateway(self):
        with tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER) as directory:
            data_folder = Path(directory)
            with patch.object(config, "DATA_FOLDER", data_folder):
                # 1. Add task
                reply = action_gateway.execute("add_task", {"text": "Write project report"}, lambda prompt: "yes")
                self.assertIn("Task saved", reply)
                self.assertIn("Write project report", reply)

                # 2. List tasks
                tasks_view = skills.list_tasks()
                self.assertIn("1. [ ] Write project report", tasks_view)

                # 3. Complete task
                comp_reply = action_gateway.execute("complete_task", {"index": 1}, lambda prompt: "yes")
                self.assertIn("Marked task 1 as completed", comp_reply)
                self.assertIn("1. [x] Write project report", skills.list_tasks())

                # 4. Delete task
                del_reply = action_gateway.execute("delete_task", {"index": 1}, lambda prompt: "yes")
                self.assertIn("Deleted task 1", del_reply)
                self.assertIn("No tasks saved yet", skills.list_tasks())

    def test_direct_task_call_fails_without_gateway(self):
        """Direct invocation of state-changing task functions must be rejected."""
        with self.assertRaises(PermissionError):
            skills.add_task("Bypass attempt")
        with self.assertRaises(PermissionError):
            skills.complete_task(1)
        with self.assertRaises(PermissionError):
            skills.delete_task(1)


class SystemHealthAndWeatherTests(unittest.TestCase):
    """Check system status, battery, and weather queries."""

    def test_system_status_read_only(self):
        status = action_gateway.execute("system_status", {}, lambda prompt: "yes")
        self.assertIn("System Status", status)
        self.assertIn("CPU:", status)

    def test_battery_status_read_only(self):
        battery = action_gateway.execute("battery_status", {}, lambda prompt: "yes")
        self.assertTrue(isinstance(battery, str) and len(battery) > 0)

    def test_weather_service_query(self):
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = mock_url.return_value.__enter__.return_value
            mock_resp.read.return_value = b"London: Sunny +18C\n"
            reply = action_gateway.execute("get_weather", {"location": "London"}, lambda prompt: "yes")
            self.assertIn("London: Sunny +18C", reply)


class TimerAndClipboardTests(unittest.TestCase):
    """Check in-memory timers and clipboard helper."""

    def test_set_and_list_timer(self):
        with patch("threading.Timer") as mock_timer_cls:
            mock_timer = mock_timer_cls.return_value
            reply = action_gateway.execute("set_timer", {"seconds": 300, "message": "Stretch"}, lambda prompt: "yes")
            self.assertIn("Timer set for 5 minute(s)", reply)
            mock_timer.start.assert_called_once()
            timers = skills.list_timers()
            self.assertIn("Stretch", timers)

    def test_clipboard_operations(self):
        with patch("tkinter.Tk") as mock_tk:
            mock_root = mock_tk.return_value
            mock_root.clipboard_get.return_value = "hello clipboard"
            read_reply = action_gateway.execute("read_clipboard", {}, lambda prompt: "yes")
            self.assertIn("hello clipboard", read_reply)

            copy_reply = action_gateway.execute("copy_to_clipboard", {"text": "new data"}, lambda prompt: "yes")
            self.assertIn("Copied 8 characters", copy_reply)


class TaskPlannerNewCommandsTests(unittest.TestCase):
    """Check command parsing for new skills in task planner."""

    def test_parse_task_and_utility_commands(self):
        parsed = task_planner._parse_local("add task Drink water")
        self.assertEqual(parsed, ("add_task", {"text": "Drink water"}))

        parsed = task_planner._parse_local("tasks")
        self.assertEqual(parsed, ("list_tasks", {}))

        parsed = task_planner._parse_local("complete task 2")
        self.assertEqual(parsed, ("complete_task", {"index": 2}))

        parsed = task_planner._parse_local("set timer for 10 minutes: Meeting")
        self.assertEqual(parsed, ("set_timer", {"seconds": 600, "message": "Meeting"}))

        parsed = task_planner._parse_local("system status")
        self.assertEqual(parsed, ("system_status", {}))

        parsed = task_planner._parse_local("battery")
        self.assertEqual(parsed, ("battery_status", {}))

        parsed = task_planner._parse_local("weather in Paris")
        self.assertEqual(parsed, ("get_weather", {"location": "Paris"}))

        parsed = task_planner._parse_local("read clipboard")
        self.assertEqual(parsed, ("read_clipboard", {}))
