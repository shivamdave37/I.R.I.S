"""Check typed update requests, isolated AI prompts, and suggestion limits."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import ai
from iris.tasks import TaskState
from updater import triggers


class TriggerTests(unittest.TestCase):
    """Verify proposal creation is explicit and deterministic suggestions are bounded."""

    def setUp(self):
        """Start every trigger test with a clean session counter and chat history."""
        triggers.reset_session_state()
        self.history = list(ai.CHAT_HISTORY)
        ai.CHAT_HISTORY = [{"role": "user", "content": "unrelated earlier chat"}]

    def tearDown(self):
        """Restore the prior chat history and clear suggestion state."""
        ai.CHAT_HISTORY = self.history
        triggers.reset_session_state()

    def test_request_generates_one_file_and_isolates_chat_history(self):
        """The AI sees only the selected file and instruction, then history is restored."""
        response = json.dumps({"files": {"router.py": "value = 2\n"}, "reason": "Fix one small issue."})
        seen = []

        def fake_ai(messages):
            """Capture the one prompt supplied to the patch generator."""
            seen.append((messages, list(ai.CHAT_HISTORY)))
            return response

        with patch.object(triggers, "_read_target", return_value="source code only\n"), \
                patch("ai.ask_ai", side_effect=fake_ai):
            files, reason = triggers._request_json("router.py", "make a small improvement")
        prompt = seen[0][0][0]["content"]
        self.assertEqual(seen[0][1], [])
        self.assertIn("source code only", prompt)
        self.assertIn("make a small improvement", prompt)
        self.assertNotIn("unrelated earlier chat", prompt)
        self.assertEqual(files, {"router.py": "value = 2\n"})
        self.assertTrue(reason.startswith("AI wrote this reason:"))
        self.assertEqual(ai.CHAT_HISTORY[0]["content"], "unrelated earlier chat")

    def test_invalid_ai_json_gets_only_one_retry(self):
        """Malformed model output is retried once and then fails safely."""
        with patch.object(triggers, "_read_target", return_value="source\n"), \
                patch("ai.ask_ai", side_effect=["not json", "still not json"]) as ask_ai:
            with self.assertRaises(ValueError):
                triggers._request_json("router.py", "small edit")
        self.assertEqual(ask_ai.call_count, 2)

    def test_protected_target_is_refused_before_ai(self):
        """A protected file target returns the fixed Codex/Antigravity message."""
        with patch("ai.ask_ai") as ask_ai:
            proposal, result = triggers.prepare_proposal("confirm.py", "change the prompt")
        self.assertIsNone(proposal)
        self.assertEqual(result, "This part is protected. Use Codex and Antigravity for it.")
        ask_ai.assert_not_called()

    def test_ai_candidate_enters_the_static_and_sandbox_pipeline(self):
        """A valid AI response is passed only to the deterministic patch pipeline."""
        candidate = SimpleNamespace(id="123456789abc", status="READY", test_result={"passed": True})
        with patch.object(triggers, "_request_json", return_value=({"iris/agent_planner.py": "safe = True\n"}, "AI wrote this reason: Small update.")), \
                patch.object(triggers.patcher, "build_proposal", return_value=candidate) as build:
            proposal, message = triggers.prepare_proposal("planner", "prefer shorter plans")
        self.assertIs(proposal, candidate)
        self.assertIn("show update 123456789abc", message)
        build.assert_called_once_with({"iris/agent_planner.py": "safe = True\n"},
                                      "AI wrote this reason: Small update.", requested_by="admin",
                                      revisions=0, run_tests=True)

    def test_update_request_needs_typed_command_and_supports_change_to_syntax(self):
        """Voice cannot request an update; typed change syntax reaches proposal prep."""
        with patch.object(triggers, "prepare_proposal", return_value=(None, "prepared")) as prepare:
            handled, response = triggers.handle_command("change planner to shorten plans", typed=False)
            self.assertTrue(handled)
            self.assertIn("typed", response)
            handled, response = triggers.handle_command("change planner to shorten plans", typed=True)
        self.assertTrue(handled)
        self.assertEqual(response, "prepared")
        prepare.assert_called_once_with("planner", "shorten plans", requested_by="admin")

    def test_stage_six_change_skill_command_is_left_to_learned_skills(self):
        """The earlier learned-skill command keeps its original route."""
        handled, _ = triggers.handle_command("change skill coin that use a fair flip", typed=True)
        self.assertFalse(handled)

    def test_suggestion_requires_three_failures_and_is_rate_limited(self):
        """Fixed code-state counters show one suggestion per hour."""
        task = SimpleNamespace(plan=["chat"], state=TaskState.DONE, command_text="unmatched phrase")
        self.assertIsNone(triggers.observe_task(task, now=10000))
        self.assertIsNone(triggers.observe_task(task, now=10001))
        self.assertIn("Suggestion:", triggers.observe_task(task, now=10002))
        other = SimpleNamespace(plan=["chat"], state=TaskState.DONE, command_text="another unmatched phrase")
        self.assertIsNone(triggers.observe_task(other, now=12000))
        self.assertIsNone(triggers.observe_task(other, now=13000))
        self.assertIn("Suggestion:", triggers.observe_task(other, now=14003))

    def test_first_suggestion_is_not_delayed_by_system_uptime(self):
        """A fresh process may suggest immediately after its third matching failure."""
        task = SimpleNamespace(plan=["chat"], state=TaskState.DONE, command_text="uptime independent")
        self.assertIsNone(triggers.observe_task(task, now=1))
        self.assertIsNone(triggers.observe_task(task, now=2))
        self.assertIsNotNone(triggers.observe_task(task, now=3))

    def test_ignore_silences_same_reason_for_session(self):
        """The typed ignore reply suppresses future notices for the same reason."""
        task = SimpleNamespace(plan=["chat"], state=TaskState.DONE, command_text="same unknown request")
        triggers.observe_task(task, now=10000)
        triggers.observe_task(task, now=10001)
        self.assertIsNotNone(triggers.observe_task(task, now=10002))
        handled, _ = triggers.handle_command("ignore", typed=True)
        self.assertTrue(handled)
        self.assertIsNone(triggers.observe_task(task, now=20000))

    def test_prepare_it_is_the_only_suggestion_action_that_requests_ai(self):
        """A suggestion itself does not prepare a patch until typed prepare it."""
        task = SimpleNamespace(plan=["chat"], state=TaskState.DONE, command_text="repeat fallback")
        triggers.observe_task(task, now=10000)
        triggers.observe_task(task, now=10001)
        triggers.observe_task(task, now=10002)
        with patch.object(triggers, "prepare_proposal", return_value=(None, "no proposal")) as prepare:
            handled, response = triggers.handle_command("prepare it", typed=True)
        self.assertTrue(handled)
        self.assertEqual(response, "no proposal")
        prepare.assert_called_once()


if __name__ == "__main__":
    unittest.main()
