"""Offline tests for approval-gated Stage 6 app and website settings."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import config
import router
from iris.agent_planner import plan
from iris.permissions import PermissionManager, SENSITIVE_RESOURCES
from iris.tasks import Task
from skills import user_config


class UserConfigTests(unittest.TestCase):
    """Check validation, confirmation, storage, and learned routing."""

    def setUp(self):
        """Give each test a private project and data directory."""
        self.temp_folder = tempfile.TemporaryDirectory(dir=config.PROJECT_FOLDER)
        self.project_folder = self.temp_folder.name
        self.data_folder = os.path.join(self.project_folder, "data")
        self.project_patch = patch.object(config, "PROJECT_FOLDER", self.project_folder)
        self.data_patch = patch.object(config, "DATA_FOLDER", self.data_folder)
        self.project_patch.start()
        self.data_patch.start()
        self.addCleanup(self.project_patch.stop)
        self.addCleanup(self.data_patch.stop)
        self.addCleanup(self.temp_folder.cleanup)
        user_config._WARNED_LOAD_STATE = None

    def test_add_website_requires_typed_yes_and_saves_https_url(self):
        """Save a normalized HTTPS site only after keyboard approval."""
        with patch("skills.user_config.request_input", return_value="yes"):
            self.assertEqual(user_config.add_website("My Site", "example.com/path"), "Added website my site.")
        with open(os.path.join(self.data_folder, "user_config.json"), encoding="utf-8") as saved_file:
            saved = json.load(saved_file)
        self.assertEqual(saved["websites"]["my site"], "https://example.com/path")

    def test_no_confirmation_does_not_write(self):
        """Reject a no response without creating the settings file."""
        with patch("skills.user_config.request_input", return_value="no"):
            reply = user_config.add_website("demo", "https://example.com")
        self.assertIn("nothing was saved", reply)
        self.assertFalse(os.path.exists(os.path.join(self.data_folder, "user_config.json")))

    def test_spoken_or_non_exact_yes_is_rejected(self):
        """Accept only an exact typed yes from the confirmation input path."""
        for answer in ("y", "yes please", "approve"):
            with self.subTest(answer=answer), patch("skills.user_config.request_input", return_value=answer):
                self.assertIn("nothing was saved", user_config.add_website("demo", "example.com"))

    def test_invalid_names_and_urls_are_rejected(self):
        """Reject punctuation, overlong labels, and non-HTTPS destinations."""
        with patch("skills.user_config.request_input") as ask:
            self.assertIn("Names can use", user_config.add_website("bad!", "example.com"))
            self.assertIn("Names can use", user_config.add_website("x" * 31, "example.com"))
            self.assertIn("HTTPS URL", user_config.add_website("demo", "http://example.com"))
            self.assertIn("HTTPS URL", user_config.add_website("demo", "https://bad host"))
        ask.assert_not_called()

    def test_built_in_names_cannot_be_overridden_from_file_or_command(self):
        """Keep built-in app and website targets authoritative over saved data."""
        os.makedirs(self.data_folder)
        with open(os.path.join(self.data_folder, "user_config.json"), "w", encoding="utf-8") as saved_file:
            json.dump({"apps": {"notepad": "C:/bad.exe"}, "websites": {"youtube": "https://bad.example"}}, saved_file)
        self.assertNotIn("notepad", user_config.learned_apps())
        self.assertNotIn("youtube", user_config.learned_websites())
        self.assertIn("cannot be replaced", user_config.add_website("youtube", "https://example.com"))

    def test_missing_or_corrupt_file_warns_and_starts_empty(self):
        """Treat absent and damaged settings as empty without raising."""
        with self.assertLogs(level="WARNING"):
            self.assertEqual(user_config.load_user_config(), {"apps": {}, "websites": {}})
        os.makedirs(self.data_folder)
        with open(os.path.join(self.data_folder, "user_config.json"), "w", encoding="utf-8") as saved_file:
            saved_file.write("not json")
        user_config._WARNED_LOAD_STATE = None
        with self.assertLogs(level="WARNING"):
            self.assertEqual(user_config.load_user_config(), {"apps": {}, "websites": {}})

    def test_add_app_finds_shortcut_and_typed_confirmation_saves_it(self):
        """Use a matching Start Menu shortcut and persist it only after approval."""
        shortcut = os.path.join(self.project_folder, "Spotify.lnk")
        with open(shortcut, "w", encoding="utf-8"):
            pass
        with patch("skills.user_config._find_shortcut", return_value=shortcut):
            with patch("skills.user_config.request_input", return_value="yes"):
                self.assertEqual(user_config.add_app("Spotify"), "Added app spotify.")
        self.assertEqual(user_config.learned_apps()["spotify"], shortcut)

    def test_add_app_fallback_requires_existing_exe_or_lnk(self):
        """Ask for a path if no shortcut exists and validate its suffix and existence."""
        app_path = os.path.join(self.project_folder, "demo.exe")
        with open(app_path, "w", encoding="utf-8"):
            pass
        with patch("skills.user_config._find_shortcut", return_value=""):
            with patch("skills.user_config.request_input", side_effect=[app_path, "yes"]):
                self.assertEqual(user_config.add_app("demo"), "Added app demo.")
            with patch("skills.user_config.request_input", return_value=os.path.join(self.project_folder, "missing.exe")):
                self.assertIn("must exist", user_config.add_app("missing"))

    def test_remove_requires_typed_yes(self):
        """Leave a learned item unchanged when removal is not approved."""
        os.makedirs(self.data_folder)
        with open(os.path.join(self.data_folder, "user_config.json"), "w", encoding="utf-8") as saved_file:
            json.dump({"apps": {"demo": "C:/demo.exe"}, "websites": {}}, saved_file)
        with patch("skills.user_config.request_input", return_value="no"):
            self.assertIn("nothing was removed", user_config.remove_item("apps", "demo"))
        self.assertIn("demo", user_config.learned_apps())

    def test_remove_website_requires_typed_yes(self):
        """Remove a learned website only after a typed yes response."""
        os.makedirs(self.data_folder)
        with open(os.path.join(self.data_folder, "user_config.json"), "w", encoding="utf-8") as saved_file:
            json.dump({"apps": {}, "websites": {"demo": "https://example.com"}}, saved_file)
        with patch("skills.user_config.request_input", return_value="yes"):
            self.assertEqual(user_config.remove_item("websites", "demo"), "Removed website demo.")
        self.assertNotIn("demo", user_config.learned_websites())

    def test_learned_app_is_opened_by_approved_router_path(self):
        """Route a saved learned name to the normal approved app launcher."""
        os.makedirs(self.data_folder)
        with open(os.path.join(self.data_folder, "user_config.json"), "w", encoding="utf-8") as saved_file:
            json.dump({"apps": {"spotify": "C:/Spotify.exe"}, "websites": {}}, saved_file)
        with patch("skills.apps.shutil.which", return_value="C:/Spotify.exe"):
            with patch("skills.apps.launch_app") as launch:
                self.assertEqual(router.handle("open spotify"), "Opening spotify.")
        launch.assert_called_once_with("C:/Spotify.exe")
        with patch("iris.agent_planner.ask_ai", side_effect=AssertionError("AI should not plan a known learned app")):
            self.assertEqual(plan("open spotify")["steps"], ["open"])

    def test_management_commands_require_iris(self):
        """Refuse learned-list changes when Iris permission controls are disabled."""
        with patch.object(config, "USE_IRIS", False):
            self.assertIn("Enable Iris", router.handle("add website demo example.com"))
        with patch.object(config, "USE_IRIS", True), patch.object(router.user_config, "handle", return_value="managed"):
            self.assertEqual(router.handle("list apps"), "managed")

    def test_user_config_resource_is_sensitive_and_requires_typed_yes(self):
        """Require per-use sensitive permission for the learned settings file."""
        self.assertIn("USER_CONFIG_FILE", SENSITIVE_RESOURCES)
        manager = PermissionManager(data_folder=self.data_folder)
        task = Task(1, "add app demo", "add app demo", needed_resources=["USER_CONFIG_FILE"], plan=["user_config"])
        with patch("iris.permissions.input_broker.create_request", return_value={"id": 1}), \
                patch("iris.permissions.input_broker.enqueue"), \
                patch("iris.permissions.input_broker.wait_for_answer", return_value="yes"):
            self.assertTrue(manager.request(task))
        with patch("iris.permissions.input_broker.create_request", return_value={"id": 2}), \
                patch("iris.permissions.input_broker.enqueue"), \
                patch("iris.permissions.input_broker.wait_for_answer", return_value="session"):
            self.assertFalse(manager.request(task))


if __name__ == "__main__":
    unittest.main()
