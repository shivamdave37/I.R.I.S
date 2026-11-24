"""Mock-only coverage for optional screen capture, vision, and UI actions."""

import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import action_gateway
import ai
import screen_capture
import screen_vision
import task_planner
import ui_automation


class FakeImage:
    size = (640, 480)

    def save(self, stream, format):
        self.assert_format = format
        stream.write(b"\x89PNG\r\n\x1a\nmock-image-data")


class FakeUiTarget:
    def __init__(self, name="Save", is_password=False, control_type="Button", runtime_id=(1,)):
        self.element_info = SimpleNamespace(
            control_type=control_type, name=name, class_name=control_type,
            automation_id="test-control", runtime_id=runtime_id, handle=123,
            process_id=123, element=SimpleNamespace(CurrentIsPassword=is_password),
        )
        self.visible = True
        self.enabled = True
        self.click_input = Mock()

    def rectangle(self):
        return SimpleNamespace(left=0, top=0, right=640, bottom=480)

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def parent(self):
        return None


def fake_frame(frame_id=None):
    payload = b"\x89PNG\r\n\x1a\nmock-image-data"
    return screen_capture.ScreenFrame(
        frame_id or __import__("hashlib").sha256(payload).hexdigest(), 640, 480,
        payload, "2026-01-01T00:00:00+00:00",
    )


class ScreenAutomationTests(unittest.TestCase):
    def setUp(self):
        self.old_frame = screen_capture._LATEST_FRAME
        screen_capture._LATEST_FRAME = None

    def tearDown(self):
        screen_capture._LATEST_FRAME = self.old_frame

    def _mock_capture(self):
        return patch.multiple(
            screen_capture, **{
                "platform": types.SimpleNamespace(system=lambda: "Windows"),
                "importlib": types.SimpleNamespace(
                    import_module=lambda name: types.SimpleNamespace(screenshot=FakeImage)
                ),
            }
        )

    def test_capture_requires_approval_and_denial_prevents_capture(self):
        with patch.object(screen_capture.importlib, "import_module") as load_dependency:
            with self.assertRaises(action_gateway.ApprovalDenied):
                action_gateway.execute("capture_screen", {}, lambda prompt: "no")
        load_dependency.assert_not_called()

    def test_approved_capture_is_ephemeral_and_does_not_write_files(self):
        with self._mock_capture(), patch("builtins.open", side_effect=AssertionError("disk write")), \
                patch("io.open", side_effect=AssertionError("disk write")), \
                patch("os.open", side_effect=AssertionError("disk write")):
            result = action_gateway.execute("capture_screen", {}, lambda prompt: "yes")
        self.assertIn("was not saved", result)
        self.assertIsNotNone(screen_capture.latest_frame())

    def test_unavailable_capture_dependency_and_capture_exception_are_reported(self):
        with patch("screen_capture.platform.system", return_value="Windows"), \
                patch("screen_capture.importlib.import_module", side_effect=ImportError):
            reply = action_gateway.execute("capture_screen", {}, lambda prompt: "yes")
        self.assertIn("Screen capture unavailable", reply)
        with patch("screen_capture.platform.system", return_value="Windows"), \
                patch("screen_capture.importlib.import_module", return_value=types.SimpleNamespace(
                    screenshot=Mock(side_effect=OSError("private")))):
            reply = action_gateway.execute("capture_screen", {}, lambda prompt: "yes")
        self.assertIn("could not capture", reply)
        self.assertNotIn("private", reply)

    def test_vision_transfer_requires_its_own_typed_approval(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        prompt = []
        with patch.dict(os.environ, {"IRIS_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}), \
                patch.object(screen_vision.ai, "_load_env_file", return_value=True), \
                patch.object(screen_vision.ai, "describe_screen", return_value="Visible: a test window.") as analyze:
            with self.assertRaises(action_gateway.ApprovalDenied):
                action_gateway.execute(
                    "analyze_screen", {"frame_id": frame.frame_id, "question": "What is visible?"},
                    lambda text: prompt.append(text) or "no",
                )
            analyze.assert_not_called()
            def replace_frame_during_approval(text):
                prompt.append(text)
                screen_capture._LATEST_FRAME = fake_frame("b" * 64)
                return "yes"

            reply = action_gateway.execute(
                "analyze_screen", {"frame_id": frame.frame_id, "question": "What is visible?"},
                replace_frame_during_approval,
            )
        self.assertIn("may contain private information", prompt[-1])
        analyze.assert_called_once_with(frame.png_bytes, "What is visible?")
        self.assertEqual(reply, "Visible: a test window.")

    def test_unsupported_vision_provider_does_not_send_image(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        with patch.dict(os.environ, {"IRIS_AI_PROVIDER": "ollama"}), \
                patch.object(screen_vision.ai, "_load_env_file", return_value=True), \
                patch.object(screen_vision.ai, "describe_screen") as analyze:
            with self.assertRaisesRegex(action_gateway.InvalidAction, "does not support"):
                action_gateway.execute(
                    "analyze_screen", {"frame_id": frame.frame_id, "question": "Describe it."},
                    lambda prompt: "yes",
                )
        analyze.assert_not_called()

    def test_ai_vision_prompt_treats_screen_text_as_untrusted(self):
        image = b"png-test"
        response = {"candidates": [{"content": {"parts": [{"text": "A window is visible."}]}}]}
        with patch.object(ai, "_load_env_file", return_value=True), \
                patch.dict(os.environ, {"IRIS_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}), \
                patch.object(ai, "_request_json", return_value=response) as request:
            result = ai.describe_screen(image, "Describe the screen.")
        payload = request.call_args.args[1]
        prompt = payload["contents"][0]["parts"][0]["text"]
        self.assertIn("untrusted content", prompt)
        self.assertIn("A window is visible", result)

    def test_invalid_ui_parameters_fail_closed(self):
        with self.assertRaises(action_gateway.InvalidAction):
            action_gateway.execute(
                "ui_click", {"frame_id": "a" * 64, "x": -1, "y": 2}, lambda prompt: "yes"
            )
        with self.assertRaises(action_gateway.InvalidAction):
            action_gateway.execute(
                "ui_type", {"frame_id": "a" * 64, "x": 2, "y": 2, "text": "\nrun"},
                lambda prompt: "yes",
            )

    def test_ui_actions_get_individual_approvals_and_denial_blocks_dispatch(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        prepared = ui_automation.PreparedTarget("target-hash", "Button 'Save'")
        fake_ui = types.SimpleNamespace(
            PreparedTarget=ui_automation.PreparedTarget,
            prepare_target=Mock(return_value=prepared),
            click_target=Mock(return_value="Click sent."),
            type_into_target=Mock(return_value="Text sent."),
        )
        prompts = []
        params_click = {"frame_id": frame.frame_id, "x": 100, "y": 80}
        params_type = {**params_click, "text": "hello"}
        with patch.dict(sys.modules, {"ui_automation": fake_ui}):
            with self.assertRaises(action_gateway.ApprovalDenied):
                action_gateway.execute("ui_click", params_click, lambda prompt: "no")
            self.assertEqual(fake_ui.click_target.call_count, 0)
            action_gateway.execute("ui_click", params_click, lambda prompt: prompts.append(prompt) or "yes")
            action_gateway.execute("ui_type", params_type, lambda prompt: prompts.append(prompt) or "yes")
        self.assertEqual(len(prompts), 2)
        self.assertIn("100, 80", prompts[0])
        self.assertIn("'hello'", prompts[1])
        self.assertEqual(fake_ui.click_target.call_count, 1)
        self.assertEqual(fake_ui.type_into_target.call_count, 1)

    def test_mocked_click_and_text_operations_dispatch_after_separate_approvals(self):
        """Only the approved accessible control receives each mocked operation."""
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        click_target = FakeUiTarget("Save", control_type="Button")
        type_target = FakeUiTarget("Search", control_type="Edit")
        type_target.set_edit_text = Mock()
        prompts = []

        def prepare(target, control_type, fingerprint):
            return (target, control_type, fingerprint, f"{control_type} {target.element_info.name!r}")

        with patch.object(ui_automation, "_uia_target", side_effect=[
                prepare(click_target, "Button", "click-id"),
                prepare(click_target, "Button", "click-id"),
                prepare(type_target, "Edit", "type-id"),
                prepare(type_target, "Edit", "type-id"),
        ]), patch.object(screen_capture, "_capture_frame", return_value=frame):
            click_reply = action_gateway.execute(
                "ui_click", {"frame_id": frame.frame_id, "x": 100, "y": 80},
                lambda prompt: prompts.append(prompt) or "yes",
            )
            type_reply = action_gateway.execute(
                "ui_type", {"frame_id": frame.frame_id, "x": 100, "y": 80, "text": "find this"},
                lambda prompt: prompts.append(prompt) or "yes",
            )

        click_target.click_input.assert_called_once_with()
        type_target.set_edit_text.assert_called_once_with("find this")
        self.assertEqual(len(prompts), 2)
        self.assertIn("'Save'", prompts[0])
        self.assertIn("find this", prompts[1])
        self.assertIn("unverified", click_reply)
        self.assertIn("unverified", type_reply)

    def test_ui_screenshot_change_after_approval_prevents_click(self):
        frame = fake_frame()
        changed = fake_frame("b" * 64)
        screen_capture._LATEST_FRAME = frame
        target = Mock()
        with patch.object(ui_automation, "_uia_target", return_value=(
                target, "Button", "fingerprint", "Button 'Save'")), \
                patch.object(screen_capture, "_capture_frame", return_value=changed):
            prepared = ui_automation.prepare_target("ui_click", {
                "frame_id": frame.frame_id, "x": 100, "y": 80,
            })
            params = {"frame_id": frame.frame_id, "x": 100, "y": 80}
            result = action_gateway.execute("ui_click", params, lambda prompt: "yes")
        self.assertIn("screen changed after approval", result)
        target.click_input.assert_not_called()

    def test_changed_accessibility_target_after_approval_prevents_click(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        old_target, new_target = FakeUiTarget(runtime_id=(1,)), FakeUiTarget(runtime_id=(2,))
        params = {"frame_id": frame.frame_id, "x": 100, "y": 80}
        with patch.object(ui_automation, "_uia_target", side_effect=[
                (old_target, "Button", "old-target", "Button 'Save'"),
                (new_target, "Button", "new-target", "Button 'Pay now'"),
        ]), patch.object(screen_capture, "_capture_frame", return_value=frame):
            result = action_gateway.execute("ui_click", params, lambda prompt: "yes")
        self.assertIn("UI target changed after approval", result)
        new_target.click_input.assert_not_called()

    def test_password_and_financial_targets_are_refused(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        for target, message in (
            (FakeUiTarget("Password", is_password=True, control_type="Edit"), "password"),
            (FakeUiTarget("Confirm payment"), "password, security, financial"),
        ):
            desktop = SimpleNamespace(from_point=lambda x, y, item=target: item)
            with patch.object(ui_automation, "_process_name", return_value="notepad.exe"), \
                    patch.object(ui_automation.importlib, "import_module", return_value=SimpleNamespace(
                        Desktop=lambda **kwargs: desktop)):
                with self.assertRaisesRegex(RuntimeError, message):
                    ui_automation.prepare_target("ui_click", {
                        "frame_id": frame.frame_id, "x": 100, "y": 80,
                    })

    def test_unknown_app_process_is_refused(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        target = FakeUiTarget()
        desktop = SimpleNamespace(from_point=lambda x, y: target)
        with patch.object(ui_automation, "_process_name", return_value="chrome.exe"), \
                patch.object(ui_automation.importlib, "import_module", return_value=SimpleNamespace(
                    Desktop=lambda **kwargs: desktop)):
            with self.assertRaisesRegex(RuntimeError, "allowlist"):
                ui_automation.prepare_target("ui_click", {
                    "frame_id": frame.frame_id, "x": 100, "y": 80,
                })

    def test_ui_dispatch_result_is_reported_as_unverified(self):
        step = task_planner.PlanStep("step_1", "ui_click", {})
        with patch.object(task_planner.action_gateway, "execute", return_value=(
                "UI action unverified: click request sent; app state was not confirmed.")):
            summary = task_planner._execute([step], lambda prompt: "yes")
        self.assertEqual(step.status, "unverified")
        self.assertIn("1 unverified", summary)

    def test_ai_proposed_ui_action_is_rejected(self):
        payload = '{"steps":[{"id":"step_1","skill":"ui_click","params":{"frame_id":"' + "a" * 64 + '","x":1,"y":2},"depends_on":[]}]}'
        with patch.object(task_planner.ai, "plan_request", return_value=payload):
            with self.assertRaisesRegex(ValueError, "explicit local commands"):
                task_planner._model_plan("please do the click")

    def test_terminal_commands_use_only_the_latest_explicit_capture(self):
        frame = fake_frame()
        screen_capture._LATEST_FRAME = frame
        self.assertEqual(task_planner._parse_local("capture screen"), ("capture_screen", {}))
        self.assertEqual(task_planner._parse_local("describe screen"), (
            "analyze_screen", {"frame_id": frame.frame_id, "question": "Describe the visible screen."}
        ))
        self.assertEqual(task_planner._parse_local("click 120 220"), (
            "ui_click", {"frame_id": frame.frame_id, "x": 120, "y": 220}
        ))
        self.assertEqual(task_planner._parse_local("type at 300,200: hello"), (
            "ui_type", {"frame_id": frame.frame_id, "x": 300, "y": 200, "text": "hello"}
        ))

    def test_optional_gui_imports_do_not_happen_for_help(self):
        with patch("builtins.__import__", side_effect=AssertionError("unexpected UI import")):
            # This test uses already-loaded modules, and help has no screen dependency.
            self.assertEqual(task_planner._parse_local("help"), ("help", {}))


if __name__ == "__main__":
    unittest.main()
