#!/usr/bin/env python3
"""Exercise combined approval, verified saving, and the subagent contract."""

from __future__ import annotations

from dataclasses import dataclass
import unittest
from unittest.mock import patch


@dataclass(frozen=True)
class ToolSchema:
    dispatch: bool = True
    join: bool = True
    models: tuple[str, ...] = ("model.test",)
    reasoning: tuple[str, ...] = ("low", "medium", "high")


class MockRuntime:
    def __init__(self, schema: ToolSchema = ToolSchema()) -> None:
        self.schema = schema
        self.events: list[tuple[str, object]] = []
        self._next_handle = 1
        self.statuses: dict[str, str] = {}
        self.files: dict[str, bytes] = {}
        self.fail_write = False
        self.fail_read = False
        self.readback_override: bytes | None = None
        self.fail_activation = False

    def inspect(self) -> ToolSchema:
        self.events.append(("inspect_subagent_capability", self.schema))
        return self.schema

    def dispatch(
        self, tasks: list[str], model: str | None, reasoning: str | None
    ) -> list[str]:
        if not self.schema.dispatch:
            raise RuntimeError("dispatch is not available")
        if (
            model is not None and model not in self.schema.models
        ) or (
            reasoning is not None and reasoning not in self.schema.reasoning
        ):
            raise RuntimeError("selected subagent override was not accepted")
        handles = []
        for task in tasks:
            handle = f"child-{self._next_handle}"
            self._next_handle += 1
            handles.append(handle)
            self.statuses.setdefault(handle, "completed")
            self.events.append(("dispatch_subagent", (handle, task, model, reasoning)))
        return handles

    def join(self, handles: list[str]) -> dict[str, str]:
        if not self.schema.join:
            raise RuntimeError("join is not available")
        self.events.append(("join_subagents", tuple(handles)))
        return {handle: self.statuses.get(handle, "pending") for handle in handles}

    def write_goal(self, path: str, content: bytes) -> None:
        self.events.append(("write_goal_file", path))
        if self.fail_write:
            raise OSError("simulated write failure")
        self.files[path] = content

    def read_goal(self, path: str) -> bytes:
        self.events.append(("read_goal_file", path))
        if self.fail_read:
            raise OSError("simulated readback failure")
        return self.files[path] if self.readback_override is None else self.readback_override

    def activate(self) -> None:
        self.events.append(("create_goal", None))
        if self.fail_activation:
            raise RuntimeError("simulated activation failure")


class GoalProtocol:
    def __init__(self, runtime: MockRuntime) -> None:
        self.runtime = runtime
        self.enabled = False
        self.model: str | None = None
        self.reasoning: str | None = None
        self.state = "discovering"
        self.draft: tuple[str, bytes] | None = None
        self.approved_draft: tuple[str, bytes] | None = None
        self.execution_intent: str | None = None
        self.launch_authorized = False

    def investigate(
        self, enabled: bool, model: str | None = None, reasoning: str | None = None
    ) -> None:
        schema = self.runtime.inspect()
        self.runtime.events.append(("ask_subagent_need", enabled))
        self.enabled = enabled
        if not enabled:
            return
        if not schema.dispatch or not schema.join:
            raise RuntimeError("parallel execution is not supported")
        self.runtime.events.append(("ask_subagent_model", model))
        self.runtime.events.append(("ask_subagent_reasoning", reasoning))
        if (model is not None and model not in schema.models) or (
            reasoning is not None and reasoning not in schema.reasoning
        ):
            raise RuntimeError("selected subagent option is not supported")
        self.model = model
        self.reasoning = reasoning

    def show_draft(self, path: str, content: bytes) -> None:
        proposed = (path, content)
        if proposed != self.draft:
            self.approved_draft = None
            self.execution_intent = None
            self.launch_authorized = False
            self.state = "drafted"
        self.draft = proposed
        self.runtime.events.append(("show_draft", proposed))

    def approve_draft(self, choice: str) -> None:
        if self.state != "drafted":
            raise RuntimeError("approval requires a displayed draft")
        self.runtime.events.append(("save_start_approval", choice))
        if choice.lower() == "n":
            return
        if choice.lower() not in {"1", "y", "2"}:
            raise ValueError("unknown save/start choice")
        self.execution_intent = "save_only" if choice == "2" else "save_and_start"
        self.launch_authorized = self.execution_intent == "save_and_start"
        self.approved_draft = self.draft
        self.state = "draft_approved"
        action = "approve_save_and_start" if self.launch_authorized else "approve_save"
        self.runtime.events.append((action, self.approved_draft))

    def verify_saved_file(self) -> None:
        if self.approved_draft is None or self.approved_draft != self.draft:
            raise RuntimeError("the displayed content and path are not approved")
        path, content = self.approved_draft
        if self.runtime.read_goal(path) != content:
            raise RuntimeError("saved content does not match the approved draft")
        self.runtime.events.append(("verify_saved_file", path))

    def save_and_maybe_start(self, tasks: list[str]) -> bool:
        if self.state != "draft_approved" or self.approved_draft != self.draft:
            raise RuntimeError("saving requires approval for the current draft")
        if self.approved_draft is None:
            raise RuntimeError("no approved draft")
        path, content = self.approved_draft
        self.runtime.write_goal(path, content)
        self.verify_saved_file()
        self.state = "saved"
        if not self.launch_authorized:
            return False
        return self.start(tasks)

    def request_start_later(self, tasks: list[str]) -> bool:
        if self.state != "saved" or self.execution_intent != "save_only":
            raise RuntimeError("a later launch request requires an unchanged saved goal")
        self.runtime.events.append(("approve_start", self.approved_draft))
        self.launch_authorized = True
        return self.start(tasks)

    def start(self, tasks: list[str]) -> bool:
        if self.state not in {"saved", "start_approved"} or not self.launch_authorized:
            raise RuntimeError("activation requires launch permission and a verified save")
        self.verify_saved_file()
        self.state = "start_approved"
        self.runtime.events.append(("start_approved", True))
        self.runtime.activate()
        self.state = "active"
        if not self.enabled:
            return True
        handles = self.runtime.dispatch(tasks, self.model, self.reasoning)
        statuses = self.runtime.join(handles)
        return (
            bool(handles)
            and set(statuses) == set(handles)
            and all(status == "completed" for status in statuses.values())
        )


def assert_event_order(events: list[tuple[str, object]], names: list[str]) -> None:
    positions = [next(i for i, event in enumerate(events) if event[0] == name) for name in names]
    if positions != sorted(positions):
        raise AssertionError(f"unexpected event order: {events}")


class GoalProtocolTests(unittest.TestCase):
    def make_protocol(self, enabled: bool = True) -> GoalProtocol:
        protocol = GoalProtocol(MockRuntime())
        protocol.investigate(enabled, "model.test", "high")
        protocol.show_draft("/project/.codex/goals/task.md", b"Approved goal\n")
        return protocol

    def assert_not_started(self, protocol: GoalProtocol) -> None:
        names = [name for name, _ in protocol.runtime.events]
        self.assertNotIn("create_goal", names)
        self.assertNotIn("dispatch_subagent", names)

    def test_one_combined_approval_saves_verifies_activates_and_dispatches(self) -> None:
        protocol = self.make_protocol()
        protocol.approve_draft("1")
        self.assertTrue(protocol.save_and_maybe_start(["one", "two"]))
        self.assertEqual(protocol.state, "active")
        assert_event_order(protocol.runtime.events, [
            "inspect_subagent_capability", "ask_subagent_need", "ask_subagent_model",
            "ask_subagent_reasoning", "show_draft", "approve_save_and_start",
            "write_goal_file", "verify_saved_file", "start_approved", "create_goal",
            "dispatch_subagent", "join_subagents",
        ])
        names = [name for name, _ in protocol.runtime.events]
        self.assertEqual(names.count("save_start_approval"), 1)
        self.assertNotIn("approve_start", names)
        self.assertNotIn("ask_start_again", names)
        dispatches = [value for name, value in protocol.runtime.events if name == "dispatch_subagent"]
        self.assertEqual(len(dispatches), 2)
        self.assertTrue(all(value[2:] == ("model.test", "high") for value in dispatches))

    def test_inherited_model_and_reasoning_omit_overrides(self) -> None:
        protocol = GoalProtocol(MockRuntime())
        protocol.investigate(True)
        protocol.show_draft("/project/goal.md", b"Goal\n")
        protocol.approve_draft("y")
        self.assertTrue(protocol.save_and_maybe_start(["one", "two"]))
        dispatches = [value for name, value in protocol.runtime.events if name == "dispatch_subagent"]
        self.assertEqual(len(dispatches), 2)
        self.assertTrue(all(value[2:] == (None, None) for value in dispatches))

    def test_disabled_subagents_continue_serially(self) -> None:
        protocol = self.make_protocol(enabled=False)
        protocol.approve_draft("Y")
        self.assertTrue(protocol.save_and_maybe_start(["serial"]))
        self.assertFalse(any(name == "dispatch_subagent" for name, _ in protocol.runtime.events))

    def test_failed_or_pending_children_prevent_completion(self) -> None:
        for status in ("failed", "pending"):
            with self.subTest(status=status):
                protocol = self.make_protocol()
                protocol.runtime.statuses["child-2"] = status
                protocol.approve_draft("1")
                self.assertFalse(protocol.save_and_maybe_start(["one", "two"]))

    def test_join_requires_exactly_all_dispatched_handles(self) -> None:
        for result in ({}, {"child-1": "completed"}, {
            "child-1": "completed", "child-2": "completed", "unrelated": "completed",
        }):
            with self.subTest(result=result):
                protocol = self.make_protocol()
                protocol.approve_draft("1")
                with patch.object(protocol.runtime, "join", return_value=result):
                    self.assertFalse(protocol.save_and_maybe_start(["one", "two"]))

    def test_missing_dispatch_or_join_is_reported_before_approval(self) -> None:
        for schema in (ToolSchema(dispatch=False), ToolSchema(join=False)):
            with self.subTest(schema=schema):
                protocol = GoalProtocol(MockRuntime(schema))
                with self.assertRaisesRegex(RuntimeError, "not supported"):
                    protocol.investigate(True, "model.test", "high")
                self.assert_not_started(protocol)

    def test_save_requires_approval_and_rejection_does_not_write(self) -> None:
        for choice in (None, "n", "N"):
            with self.subTest(choice=choice):
                protocol = self.make_protocol()
                if choice is not None:
                    protocol.approve_draft(choice)
                with self.assertRaisesRegex(RuntimeError, "requires approval"):
                    protocol.save_and_maybe_start(["one"])
                self.assertEqual(protocol.runtime.files, {})
                self.assert_not_started(protocol)

    def test_launch_permission_cannot_skip_saving(self) -> None:
        protocol = self.make_protocol()
        protocol.approve_draft("1")
        with self.assertRaisesRegex(RuntimeError, "verified save"):
            protocol.start(["one"])
        self.assert_not_started(protocol)

    def test_failed_write_or_readback_never_starts_and_unchanged_retry_reuses_approval(self) -> None:
        for failure in ("write", "read", "mismatch"):
            with self.subTest(failure=failure):
                protocol = self.make_protocol()
                protocol.approve_draft("1")
                protocol.runtime.fail_write = failure == "write"
                protocol.runtime.fail_read = failure == "read"
                protocol.runtime.readback_override = b"Wrong content\n" if failure == "mismatch" else None
                with self.assertRaises((OSError, RuntimeError)):
                    protocol.save_and_maybe_start(["one", "two"])
                self.assertEqual(protocol.state, "draft_approved")
                self.assert_not_started(protocol)
                self.assertFalse(any(name == "verify_saved_file" for name, _ in protocol.runtime.events))
                protocol.runtime.fail_write = False
                protocol.runtime.fail_read = False
                protocol.runtime.readback_override = None
                self.assertTrue(protocol.save_and_maybe_start(["one", "two"]))
                self.assertEqual(sum(name == "save_start_approval" for name, _ in protocol.runtime.events), 1)

    def test_save_only_stops_saved_until_a_later_explicit_launch_request(self) -> None:
        protocol = self.make_protocol()
        protocol.approve_draft("2")
        self.assertFalse(protocol.save_and_maybe_start(["one", "two"]))
        self.assertEqual(protocol.state, "saved")
        self.assert_not_started(protocol)
        with self.assertRaisesRegex(RuntimeError, "launch permission"):
            protocol.start(["one", "two"])
        self.assertTrue(protocol.request_start_later(["one", "two"]))
        names = [name for name, _ in protocol.runtime.events]
        self.assertEqual(names.count("save_start_approval"), 1)
        self.assertEqual(names.count("approve_start"), 1)
        self.assertNotIn("ask_start_again", names)
        self.assertEqual(names.count("write_goal_file"), 1)

    def test_later_launch_rechecks_the_saved_content(self) -> None:
        protocol = self.make_protocol()
        protocol.approve_draft("2")
        protocol.save_and_maybe_start(["one"])
        protocol.runtime.readback_override = b"Modified saved content\n"
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            protocol.request_start_later(["one"])
        self.assert_not_started(protocol)

    def test_content_or_path_changes_invalidate_both_permissions(self) -> None:
        for path, content in (("/project/new-goal.md", b"Approved goal\n"), (
            "/project/.codex/goals/task.md", b"Revised goal\n",
        )):
            with self.subTest(path=path, content=content):
                protocol = self.make_protocol()
                protocol.approve_draft("1")
                protocol.show_draft(path, content)
                self.assertEqual(protocol.state, "drafted")
                self.assertIsNone(protocol.execution_intent)
                self.assertFalse(protocol.launch_authorized)
                with self.assertRaisesRegex(RuntimeError, "requires approval"):
                    protocol.save_and_maybe_start(["one"])
                with self.assertRaisesRegex(RuntimeError, "launch permission"):
                    protocol.start(["one"])
                self.assert_not_started(protocol)
                protocol.approve_draft("2")
                self.assertFalse(protocol.save_and_maybe_start(["one"]))
                self.assertEqual(protocol.runtime.files[path], content)
                self.assert_not_started(protocol)

    def test_activation_failure_never_dispatches_and_retry_reuses_approval(self) -> None:
        protocol = self.make_protocol()
        protocol.approve_draft("1")
        protocol.runtime.fail_activation = True
        with self.assertRaisesRegex(RuntimeError, "activation failure"):
            protocol.save_and_maybe_start(["one", "two"])
        self.assertEqual(protocol.state, "start_approved")
        self.assertFalse(any(name == "dispatch_subagent" for name, _ in protocol.runtime.events))
        protocol.runtime.fail_activation = False
        self.assertTrue(protocol.start(["one", "two"]))
        self.assertEqual(sum(name == "save_start_approval" for name, _ in protocol.runtime.events), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
