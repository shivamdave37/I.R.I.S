"""Offline tests for approval-gated Stage 6 app and website settings."""

import io
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import config
import main
import router
from iris.agent_planner import plan
from iris.permissions import PermissionManager, SENSITIVE_RESOURCES
from iris.resources import ResourceManager
from iris.tasks import Task
from iris import wake
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


class WakeWordTests(unittest.TestCase):
    """Check offline wake detection, fallbacks, and audio resource ownership."""

    def test_wake_is_disabled_by_default(self):
        """Keep wake listening off until the user changes the setting."""
        self.assertFalse(config.WAKE_ENABLED)
        self.assertFalse(wake.create_listener()["enabled"])

    def test_one_audio_chunk_can_contain_wake_word_and_command(self):
        """Decode a command from the same phrase as its wake word."""
        audio = object()
        listener = {"enabled": True, "offline": True, "model": object()}
        with patch("iris.wake._capture", return_value=("audio", audio)) as capture:
            with patch("iris.wake._recognized_text", side_effect=["iris [unk]", "hey iris open youtube"]) as recognize:
                status, command = wake.listen_chunk(ResourceManager(), listener)
        self.assertEqual((status, command), ("wake", "open youtube"))
        self.assertEqual(recognize.call_count, 2)
        self.assertEqual(json.loads(recognize.call_args_list[0].args[2]), ["iris", "[unk]"])
        capture.assert_called_once()

    def test_vosk_runtime_error_is_labeled_and_uses_online_fallback(self):
        """Keep the loop running if the offline decoder fails after startup."""
        audio = object()
        listener = {"enabled": True, "offline": True, "model": object()}
        with patch("iris.wake._capture", return_value=("audio", audio)):
            with patch("iris.wake._recognized_text", side_effect=["iris", RuntimeError("decoder")]):
                with patch("iris.wake.voice.recognize_audio", return_value="hey iris open youtube"):
                    with patch("sys.stdout", new_callable=io.StringIO) as output:
                        self.assertEqual(wake.listen_chunk(ResourceManager(), listener), ("wake", "open youtube"))
        self.assertFalse(listener["offline"])
        self.assertIn("online fallback", output.getvalue())

    def test_vosk_missing_model_selects_clear_online_fallback(self):
        """Use the labeled online mode when the configured model folder is absent."""
        with patch.object(config, "WAKE_ENABLED", True), patch.object(config, "WAKE_MODEL_PATH", "missing-model-folder"):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                listener = wake.create_listener()
        self.assertTrue(listener["enabled"])
        self.assertFalse(listener["offline"])
        self.assertIn("online fallback", output.getvalue())

    def test_online_fallback_detects_wake_and_same_phrase_command(self):
        """Use the existing online recognizer when Vosk is unavailable."""
        audio = object()
        listener = {"enabled": True, "offline": False, "model": None}
        with patch("iris.wake._capture", return_value=("audio", audio)):
            with patch("iris.wake.voice.recognize_audio", return_value="hey iris what's the time"):
                self.assertEqual(wake.listen_chunk(ResourceManager(), listener), ("wake", "what's the time"))

    def test_no_wake_word_does_not_start_a_command(self):
        """Keep ordinary speech in idle state until the configured word is heard."""
        audio = object()
        listener = {"enabled": True, "offline": False, "model": None}
        with patch("iris.wake._capture", return_value=("audio", audio)):
            with patch("iris.wake.voice.recognize_audio", return_value="what is the time"):
                self.assertEqual(wake.listen_chunk(ResourceManager(), listener), ("idle", ""))

    def test_wake_listener_does_not_open_mic_while_task_holds_resource(self):
        """Skip microphone capture when an Iris task owns MIC_SPEAKER."""
        resources = ResourceManager()
        task = Task(2, "voice task", "chat", needed_resources=["MIC_SPEAKER"])
        self.assertTrue(resources.reserve_all(task))
        listener = {"enabled": True, "offline": False, "model": None}
        with patch("iris.wake.voice.capture_audio_chunk") as capture:
            self.assertEqual(wake.listen_chunk(resources, listener), ("busy", ""))
        capture.assert_not_called()

    def test_wake_capture_waits_for_speech_and_releases_audio_lock(self):
        """Wait for queued speech before capture and release the resource afterward."""
        resources = ResourceManager()
        with patch("iris.wake.voice.wait_until_done") as wait_for_speech:
            with patch("iris.wake.voice.capture_audio_chunk", return_value=None) as capture:
                self.assertEqual(wake._capture(resources, 1, 3), ("idle", None))
        wait_for_speech.assert_called_once_with()
        capture.assert_called_once_with(timeout=1, phrase_time_limit=3)
        self.assertEqual(resources.snapshot(), {})

    def test_mic_error_requests_typed_command_in_iris_loop(self):
        """Fall back to keyboard input when wake listening cannot access the mic."""
        supervisor = Mock()
        supervisor.resources = ResourceManager()
        supervisor.pending_permission_prompt.return_value = None
        with patch("iris.iris.Iris", return_value=supervisor):
            with patch("iris.permissions.PermissionManager") as permission_type:
                permission_type.return_value.pending_prompt.return_value = None
                with patch("iris.wake.create_listener", return_value={"enabled": True, "offline": False, "model": None}):
                    with patch("iris.wake.listen_chunk", return_value=("error", "")):
                        with patch("main._keyboard_input_ready", return_value=False):
                            with patch("main.read_console_line", return_value="exit") as typed_input:
                                with patch("main.voice.wait_until_done"), patch("main.voice.shutdown"):
                                    with patch("sys.stdout", new_callable=io.StringIO):
                                        main.run_iris("both")
        typed_input.assert_called_once()


if __name__ == "__main__":
    unittest.main()
