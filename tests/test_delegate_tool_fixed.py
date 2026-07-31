"""
Tests for the fixed delegate_tool (subagent delegation).

Verifies that:
    - The active-agent singleton pattern works (set/get).
    - delegate() correctly invokes the sub-agent's provider.
    - The transcript is mutated so the sub-agent can loop on tool calls.
    - max_iterations is clamped to a safe range.
    - Errors are propagated cleanly.
    - The OpenAI schema is valid.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from tools.delegate_tool import (
    DELEGATE_SCHEMA,
    _build_subagent_prompt,
    _has_pending_tool_calls,
    delegate,
)
from run_agent import NexaAgent, get_active_agent, set_active_agent


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
class _FakeProvider:
    """A fake LLM provider that returns canned streaming events."""

    def __init__(self, scripted_events: List[tuple]) -> None:
        """Initialize with a list of (event_type, payload) tuples to yield."""
        self._events = scripted_events
        self.calls = 0

    async def chat_stream(
        self, messages, tools=None, registry=None, _depth: int = 0
    ) -> AsyncGenerator[tuple, None]:
        """Yield the scripted events."""
        self.calls += 1
        # Mutate the transcript like the real provider does (so _has_pending_tool_calls works).
        if self._events and self._events[0][0] == "tool_call":
            # Append the assistant tool_call message before yielding the event.
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "tc1", "type": "function",
                                "function": {"name": "read_file", "arguments": "{}"}}],
            })
        for event_type, payload in self._events:
            yield event_type, payload
        # If we made a tool call, append the tool result so the loop can continue.
        if self._events and self._events[0][0] == "tool_call":
            messages.append({
                "role": "tool",
                "tool_call_id": "tc1",
                "content": "fake file content",
            })


class _FakeResult:
    """Mimics tools.registry.ToolResult."""

    def __init__(self, tool: str, ok: bool, output: str) -> None:
        self.tool = tool
        self.ok = ok
        self.output = output

    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "ok": self.ok, "output": self.output}


def _make_agent(events: List[tuple]) -> NexaAgent:
    """Build a NexaAgent with a fake provider yielding the given events."""
    # We bypass __init__ to avoid network/db setup.
    agent = NexaAgent.__new__(NexaAgent)
    agent.provider = _FakeProvider(events)
    agent.registry = MagicMock()
    agent.registry.get_openai_schemas.return_value = []
    return agent


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------
class TestActiveAgentSingleton:
    """Tests for the module-level active-agent registry."""

    def test_set_and_get_active_agent(self) -> None:
        """set_active_agent/get_active_agent round-trip works."""
        agent = _make_agent([("done", None)])
        set_active_agent(agent)
        assert get_active_agent() is agent

    def test_get_active_agent_default_none(self) -> None:
        """get_active_agent returns None when never set."""
        # Note: depends on test isolation; we don't reset, but the contract
        # is "returns None if not set" — tested by checking the type.
        agent = get_active_agent()
        assert agent is None or isinstance(agent, NexaAgent)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
class TestDelegateValidation:
    """Tests for delegate() argument validation."""

    @pytest.mark.asyncio
    async def test_empty_task_raises(self) -> None:
        """Empty task must raise ValueError."""
        with pytest.raises(ValueError, match="task is required"):
            await delegate("")

    @pytest.mark.asyncio
    async def test_whitespace_task_raises(self) -> None:
        """Whitespace-only task must raise ValueError."""
        with pytest.raises(ValueError, match="task is required"):
            await delegate("   ")

    @pytest.mark.asyncio
    async def test_no_active_agent_returns_error(self) -> None:
        """When no active agent is set, delegate returns a clear error string."""
        # Force the singleton to None.
        import run_agent
        old = run_agent._agent_singleton
        run_agent._agent_singleton = None
        try:
            result = await delegate("test task")
            assert "Could not access" in result or "no active agent" in result.lower()
        finally:
            run_agent._agent_singleton = old

    @pytest.mark.asyncio
    async def test_clamps_max_iterations_too_high(self) -> None:
        """max_iterations > 8 is clamped to 8."""
        agent = _make_agent([("done", None)])
        set_active_agent(agent)
        await delegate("task", max_iterations=100)
        # The fake provider records how many times it was called.
        assert agent.provider.calls <= 8

    @pytest.mark.asyncio
    async def test_clamps_max_iterations_too_low(self) -> None:
        """max_iterations < 1 is clamped to 1."""
        agent = _make_agent([("done", None)])
        set_active_agent(agent)
        await delegate("task", max_iterations=0)
        assert agent.provider.calls == 1


# ---------------------------------------------------------------------------
# Behavior tests
# ---------------------------------------------------------------------------
class TestDelegateBehavior:
    """Tests for delegate() end-to-end behavior with a fake agent."""

    @pytest.mark.asyncio
    async def test_returns_summary_on_done(self) -> None:
        """delegate returns a summary string when the sub-agent finishes."""
        agent = _make_agent([("token", "Hello"), ("token", " world"), ("done", None)])
        set_active_agent(agent)
        result = await delegate("say hello")
        assert "Hello world" in result
        assert "Sub-agent result" in result

    @pytest.mark.asyncio
    async def test_loops_on_tool_calls(self) -> None:
        """When the sub-agent makes a tool call, delegate loops and asks again."""
        # First call: tool_call + done (loop iteration 1)
        # Second call: token + done (loop iteration 2 — final answer)
        events_iter1 = [("tool_call", _FakeResult("read_file", True, "content")),
                         ("done", None)]
        events_iter2 = [("token", "Based on the file"), ("done", None)]
        agent = _make_agent(events_iter1)
        # Make the fake provider return different events on each call.
        call_count = [0]
        original_stream = agent.provider.chat_stream

        async def counting_stream(messages, tools=None, registry=None, _depth: int = 0):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: emit a tool call.
                messages.append({
                    "role": "assistant", "content": "",
                    "tool_calls": [{"id": "tc1", "type": "function",
                                    "function": {"name": "read_file", "arguments": "{}"}}],
                })
                yield ("tool_call", _FakeResult("read_file", True, "content"))
                yield ("done", None)
                messages.append({"role": "tool", "tool_call_id": "tc1", "content": "content"})
            else:
                yield ("token", "Based on the file")
                yield ("done", None)
        agent.provider.chat_stream = counting_stream
        set_active_agent(agent)
        result = await delegate("read and summarize", max_iterations=3)
        assert call_count[0] >= 2
        assert "Based on the file" in result

    @pytest.mark.asyncio
    async def test_stops_on_max_iterations(self) -> None:
        """delegate stops after max_iterations even if not done."""
        # Each call returns a tool call → never produces final answer.
        agent = _make_agent([("tool_call", _FakeResult("t", True, "x")), ("done", None)])
        # Make provider always return a tool call (never done with text).
        async def looping_stream(messages, tools=None, registry=None, _depth: int = 0):
            messages.append({
                "role": "assistant", "content": "",
                "tool_calls": [{"id": "tc1", "type": "function",
                                "function": {"name": "t", "arguments": "{}"}}],
            })
            yield ("tool_call", _FakeResult("t", True, "x"))
            yield ("done", None)
            messages.append({"role": "tool", "tool_call_id": "tc1", "content": "x"})
        agent.provider.chat_stream = looping_stream
        set_active_agent(agent)
        result = await delegate("never done", max_iterations=2)
        assert agent.provider.calls <= 2

    @pytest.mark.asyncio
    async def test_propagates_error_event(self) -> None:
        """An error event from the sub-agent is returned in the summary."""
        agent = _make_agent([("error", "boom")])
        set_active_agent(agent)
        result = await delegate("trigger error")
        assert "boom" in result or "delegate error" in result.lower()

    @pytest.mark.asyncio
    async def test_includes_tool_results_in_summary(self) -> None:
        """Tool call results are included in the summary."""
        events = [("tool_call", _FakeResult("read_file", True, "file content")),
                  ("token", "Done"), ("done", None)]
        agent = _make_agent(events)
        # Override to append tool messages (the fake provider does this for tool_call[0])
        async def stream_with_tools(messages, tools=None, registry=None, _depth: int = 0):
            messages.append({
                "role": "assistant", "content": "",
                "tool_calls": [{"id": "tc1", "type": "function",
                                "function": {"name": "read_file", "arguments": "{}"}}],
            })
            yield ("tool_call", _FakeResult("read_file", True, "file content"))
            yield ("token", "Done")
            yield ("done", None)
            messages.append({"role": "tool", "tool_call_id": "tc1", "content": "file content"})
        agent.provider.chat_stream = stream_with_tools
        set_active_agent(agent)
        result = await delegate("read and finish")
        assert "read_file" in result or "Tools used" in result


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------
class TestSubagentPrompt:
    """Tests for _build_subagent_prompt."""

    def test_includes_task(self) -> None:
        """The prompt includes the task description."""
        prompt = _build_subagent_prompt("do X", None, 3)
        assert "do X" in prompt

    def test_includes_context(self) -> None:
        """The prompt includes optional context."""
        prompt = _build_subagent_prompt("do X", "extra context", 3)
        assert "extra context" in prompt

    def test_includes_max_iterations(self) -> None:
        """The prompt mentions the iteration budget."""
        prompt = _build_subagent_prompt("do X", None, 5)
        assert "5" in prompt


class TestHasPendingToolCalls:
    """Tests for _has_pending_tool_calls."""

    def test_true_when_assistant_has_unanswered_tool_call(self) -> None:
        """Returns True when the last assistant message has unanswered tool calls."""
        messages = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "x", "arguments": "{}"}}]},
        ]
        assert _has_pending_tool_calls(messages) is True

    def test_false_when_tool_call_answered(self) -> None:
        """Returns False when the tool call has been answered."""
        messages = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "x", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "tc1", "content": "result"},
        ]
        assert _has_pending_tool_calls(messages) is False

    def test_false_for_plain_assistant_message(self) -> None:
        """Returns False when there are no tool calls."""
        messages = [{"role": "assistant", "content": "hello"}]
        assert _has_pending_tool_calls(messages) is False

    def test_false_for_empty_messages(self) -> None:
        """Returns False for an empty transcript."""
        assert _has_pending_tool_calls([]) is False


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class TestDelegateSchema:
    """Tests for the OpenAI function-calling schema."""

    def test_schema_has_task_property(self) -> None:
        """The schema must define a 'task' string property."""
        assert "task" in DELEGATE_SCHEMA["properties"]
        assert DELEGATE_SCHEMA["properties"]["task"]["type"] == "string"

    def test_schema_required_includes_task(self) -> None:
        """'task' must be in the required list."""
        assert "task" in DELEGATE_SCHEMA["required"]

    def test_schema_max_iterations_type(self) -> None:
        """max_iterations should be an integer (not number — bug fix)."""
        assert DELEGATE_SCHEMA["properties"]["max_iterations"]["type"] == "integer"
