#!/usr/bin/env python3
"""Deterministically exercise the subagent planning/runtime contract."""

from __future__ import annotations

from dataclasses import dataclass


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

    def inspect(self) -> ToolSchema:
        self.events.append(("inspect_subagent_capability", self.schema))
        return self.schema

    def dispatch(
        self, tasks: list[str], model: str | None, reasoning: str | None
    ) -> list[str]:
        if not self.schema.dispatch:
            raise RuntimeError("dispatch is not available")
        if model not in self.schema.models or reasoning not in self.schema.reasoning:
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


class GoalProtocol:
    def __init__(self, runtime: MockRuntime) -> None:
        self.runtime = runtime
        self.enabled = False
        self.model: str | None = None
        self.reasoning: str | None = None

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
        if model not in schema.models or reasoning not in schema.reasoning:
            raise RuntimeError("selected subagent option is not supported")
        self.model = model
        self.reasoning = reasoning

    def start_after_approval(self, tasks: list[str], approved: bool) -> bool:
        if not approved:
            raise RuntimeError("dispatch attempted before the second approval")
        self.runtime.events.append(("start_approved", True))
        if not self.enabled:
            return True
        handles = self.runtime.dispatch(tasks, self.model, self.reasoning)
        statuses = self.runtime.join(handles)
        return bool(handles) and all(status == "completed" for status in statuses.values())


def assert_event_order(events: list[tuple[str, object]], names: list[str]) -> None:
    positions = [next(i for i, event in enumerate(events) if event[0] == name) for name in names]
    if positions != sorted(positions):
        raise AssertionError(f"unexpected event order: {events}")


def main() -> int:
    runtime = MockRuntime()
    protocol = GoalProtocol(runtime)
    protocol.investigate(True, "model.test", "high")
    if protocol.start_after_approval(["one", "two"], approved=True) is not True:
        raise AssertionError("completed child batch was not accepted")
    assert_event_order(
        runtime.events,
        [
            "inspect_subagent_capability",
            "ask_subagent_need",
            "ask_subagent_model",
            "ask_subagent_reasoning",
            "start_approved",
            "dispatch_subagent",
            "join_subagents",
        ],
    )
    dispatch_events = [event for event in runtime.events if event[0] == "dispatch_subagent"]
    if any(event[1][2:] != ("model.test", "high") for event in dispatch_events):
        raise AssertionError("selected model/reasoning values were not preserved")

    disabled_runtime = MockRuntime()
    disabled_protocol = GoalProtocol(disabled_runtime)
    disabled_protocol.investigate(False)
    if not disabled_protocol.start_after_approval(["serial"], approved=True):
        raise AssertionError("disabled subagent workflow did not continue serially")
    if any(event[0] == "dispatch_subagent" for event in disabled_runtime.events):
        raise AssertionError("disabled workflow dispatched a subagent")

    failing_runtime = MockRuntime()
    failing_protocol = GoalProtocol(failing_runtime)
    failing_protocol.investigate(True, "model.test", "medium")
    failing_runtime.statuses["child-2"] = "failed"
    if failing_protocol.start_after_approval(["one", "two"], approved=True):
        raise AssertionError("failed child batch was reported as complete")

    pending_runtime = MockRuntime()
    pending_protocol = GoalProtocol(pending_runtime)
    pending_protocol.investigate(True, "model.test", "low")
    pending_runtime.statuses["child-2"] = "pending"
    if pending_protocol.start_after_approval(["one", "two"], approved=True):
        raise AssertionError("pending child batch was reported as complete")

    unsupported_protocol = GoalProtocol(MockRuntime(ToolSchema(dispatch=False)))
    try:
        unsupported_protocol.investigate(True, "model.test", "medium")
    except RuntimeError:
        pass
    else:
        raise AssertionError("unsupported dispatch capability was not surfaced")

    print("Mock subagent runtime contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
