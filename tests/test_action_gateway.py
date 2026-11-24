"""Verify the centralized fail-closed policy and immediate approval order."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import action_gateway
import approval_context
import skills
import skill_development
import task_planner


class ActionGatewayTests(unittest.TestCase):
    """Ensure every dispatched action has a policy and guarded side effects."""

    def test_missing_approval_policy_is_rejected_before_dispatch(self):
        """A removed policy cannot fall back to an unapproved action."""
        with patch.dict(action_gateway.ACTION_POLICIES, {"open_target": None}), \
                patch("skills.open_approved") as opener:
            with self.assertRaises(action_gateway.InvalidAction):
                action_gateway.execute("open_target", {"target": "notepad"}, lambda prompt: "yes")
        opener.assert_not_called()

    def test_state_changing_policy_cannot_disable_approval(self):
        """A malformed or weakened policy for a known side effect fails closed."""
        policy = action_gateway.ActionPolicy(frozenset({"text"}), "state_change", False)
        with patch.dict(action_gateway.ACTION_POLICIES, {"save_note": policy}), \
                patch("skills.add_note") as save_note:
            with self.assertRaises(action_gateway.InvalidAction):
                action_gateway.execute("save_note", {"text": "test"}, lambda prompt: "yes")
        save_note.assert_not_called()

    def test_new_action_cannot_be_marked_read_only_by_default(self):
        """New actions require approval unless explicitly reviewed as read-only."""
        policy = action_gateway.ActionPolicy(frozenset(), "read_only", False)
        with patch.dict(action_gateway.ACTION_POLICIES, {"new_action": policy}):
            with self.assertRaises(action_gateway.InvalidAction):
                action_gateway.execute("new_action", {}, lambda prompt: "yes")

    def test_every_known_state_change_has_an_approval_policy(self):
        """All registered effects that change state are explicitly approval-gated."""
        self.assertTrue(action_gateway.STATE_CHANGING_ACTIONS.issubset(action_gateway.ACTION_POLICIES))
        for skill_name in action_gateway.STATE_CHANGING_ACTIONS:
            policy = action_gateway.ACTION_POLICIES[skill_name]
            self.assertEqual(policy.effect, "state_change")
            self.assertIs(policy.requires_approval, True)

    def test_unknown_action_and_invalid_arguments_are_rejected(self):
        """Neither unknown skill names nor extra parameter keys reach a handler."""
        with patch("skills.open_approved") as opener:
            with self.assertRaises(action_gateway.InvalidAction):
                action_gateway.execute("run_shell", {"command": "whoami"}, lambda prompt: "yes")
            with self.assertRaises(action_gateway.InvalidAction):
                action_gateway.execute("open_target", {"target": "notepad", "command": "x"}, lambda prompt: "yes")
        opener.assert_not_called()

    def test_approval_is_asked_immediately_before_each_side_effect(self):
        """The event order is approval, action, approval, action—not all approvals first."""
        events = []

        def ask(prompt):
            events.append(("approval", prompt))
            return "yes"

        def open_app(target):
            events.append(("open", target))
            return "Opened youtube."

        def save_note(text):
            events.append(("save", text))
            return "Note saved."

        with patch("skills.open_approved", side_effect=open_app), \
                patch("skills.add_note", side_effect=save_note), \
                redirect_stdout(io.StringIO()):
            task_planner.handle("open YouTube and note exact words", ask)

        self.assertEqual([event[0] for event in events], ["approval", "open", "approval", "save"])
        self.assertIn("'youtube'", events[0][1])
        self.assertIn("'exact words'", events[2][1])

    def test_ai_generated_registered_action_still_requires_gateway_approval(self):
        """A model can propose a skill but cannot approve its execution."""
        plan = json.dumps({"steps": [
            {"id": "step_1", "skill": "open_target", "params": {"target": "notepad"}, "depends_on": []}
        ]})
        with patch("task_planner.ai.plan_request", return_value=plan), \
                patch("skills.open_approved") as opener, \
                redirect_stdout(io.StringIO()):
            result = task_planner.handle("do something with my work tool", lambda prompt: "no")
        self.assertIn("denied", result.lower())
        opener.assert_not_called()

    def test_direct_note_and_app_skills_require_gateway_context(self):
        """Direct calls to state-changing skill functions cannot write or launch."""
        with patch("skills.shutil.which", return_value=r"C:\Windows\notepad.exe"), \
                patch("skills.os.startfile", create=True) as opener:
            with self.assertRaises(PermissionError):
                skills.add_note("direct call")
            with self.assertRaises(PermissionError):
                skills.open_approved("notepad")
        opener.assert_not_called()

    def test_direct_other_state_changing_skill_calls_require_gateway(self):
        """Delete, research, and proposal mutations cannot be called without a grant."""
        with patch("skills.ai.research_web") as research:
            with self.assertRaises(PermissionError):
                skills.delete_note(1, approved=True)
            with self.assertRaises(PermissionError):
                skills.research_web("Python testing")
            with self.assertRaises(PermissionError):
                skill_development.create_proposal("greeting", "Return a short greeting")
            with self.assertRaises(PermissionError):
                skill_development.approve_for_manual_integration("greeting", 1)
            with self.assertRaises(PermissionError):
                skill_development.withdraw_proposal("greeting", 1)
        research.assert_not_called()

    def test_approval_uses_parameter_snapshot_not_mutable_caller_dictionary(self):
        """Changing caller input while prompting cannot change the dispatched note."""
        params = {"text": "approved note"}
        prompts = []

        def mutate_while_asking(prompt):
            prompts.append(prompt)
            params["text"] = "unapproved replacement"
            return "yes"

        with patch("skills.add_note", side_effect=lambda text: f"saved:{text}") as save_note:
            result = action_gateway.execute("save_note", params, mutate_while_asking)

        self.assertIn("approved note", prompts[0])
        self.assertEqual(result, "saved:approved note")
        save_note.assert_called_once_with("approved note")

    def test_nested_parameter_snapshot_is_independent(self):
        """Nested JSON values are copied rather than retained by reference."""
        original = {"items": [{"value": "approved"}]}
        snapshot = action_gateway._snapshot_params(original)
        original["items"][0]["value"] = "changed"
        self.assertEqual(snapshot, {"items": [{"value": "approved"}]})

    def test_unsafe_parameter_value_fails_before_prompt_or_dispatch(self):
        """Non-JSON objects cannot reach an approval callback or handler."""
        ask = Mock(return_value="yes")
        with patch("skills.add_note") as save_note:
            with self.assertRaises(action_gateway.InvalidAction):
                action_gateway.execute("save_note", {"text": object()}, ask)
        ask.assert_not_called()
        save_note.assert_not_called()

    def test_direct_or_mis_scoped_approval_grants_are_rejected(self):
        """Ordinary callers cannot create a grant or reuse one for another action."""
        with self.assertRaises(PermissionError):
            with approval_context._grant("save_note", {"text": "forged"}):
                pass
        with self.assertRaises(PermissionError):
            with approval_context._grant("save_note", {"text": "forged"}, capability=object()):
                pass
        with approval_context._grant(
            "save_note", {"text": "only this note"},
            capability=approval_context._GATEWAY_CAPABILITY,
        ):
            with self.assertRaises(PermissionError):
                skills.delete_note(1, approved=True)

    def test_low_level_writers_require_matching_gateway_scope(self):
        """Internal note and audit writers reject direct unauthorized calls."""
        with self.assertRaises(PermissionError):
            skills._write_notes(["replacement"], 1)
        with self.assertRaises(PermissionError):
            skill_development._append_event(
                {"event": "proposal_withdrawn", "name": "greeting", "version": 1, "time": "test"},
                "withdraw_skill_proposal", {"name": "greeting", "version": 1},
            )


if __name__ == "__main__":
    unittest.main()
