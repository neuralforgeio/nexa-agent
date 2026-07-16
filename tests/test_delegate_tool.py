"""
Tests for the subagent delegation tool.

Verifies:
    - The delegate tool is registered in the default registry.
    - The delegate tool schema is valid OpenAI function-calling format.
    - The delegate function handles empty task errors.
    - The _build_subagent_prompt produces correct content.
    - The _has_pending_tool_calls helper works correctly.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest

from tools.registry import ToolRegistry, create_default_registry
from tools.delegate_tool import (
    DELEGATE_SCHEMA,
    _build_subagent_prompt,
    _has_pending_tool_calls,
)


class TestDelegateToolRegistration:
    """Tests that the delegate tool is properly registered."""

    def test_delegate_is_registered(self) -> None:
        """The default registry must include the delegate tool."""
        registry = create_default_registry()
        assert registry.has("delegate")

    def test_delegate_schema_is_valid(self) -> None:
        """The delegate schema must be valid OpenAI function-calling format."""
        registry = create_default_registry()
        schemas = registry.get_openai_schemas()
        delegate_schema = [s for s in schemas if s["function"]["name"] == "delegate"]
        assert len(delegate_schema) == 1

        fn = delegate_schema[0]["function"]
        assert "description" in fn
        assert fn["parameters"]["type"] == "object"
        assert "task" in fn["parameters"]["properties"]
        assert "task" in fn["parameters"]["required"]

    def test_delegate_schema_has_optional_params(self) -> None:
        """The delegate schema must include optional context and max_iterations."""
        props = DELEGATE_SCHEMA["properties"]
        assert "context" in props
        assert "max_iterations" in props
        # Only task is required.
        assert DELEGATE_SCHEMA["required"] == ["task"]


class TestSubagentPromptBuilder:
    """Tests for the _build_subagent_prompt function."""

    def test_prompt_includes_task(self) -> None:
        """The prompt must include the task description."""
        prompt = _build_subagent_prompt("Write a Python function", None, 3)
        assert "Write a Python function" in prompt

    def test_prompt_includes_context(self) -> None:
        """The prompt must include context when provided."""
        prompt = _build_subagent_prompt("Do something", "Extra context here", 3)
        assert "Extra context here" in prompt

    def test_prompt_includes_max_iterations(self) -> None:
        """The prompt must mention the iteration budget."""
        prompt = _build_subagent_prompt("Task", None, 5)
        assert "5" in prompt

    def test_prompt_works_without_context(self) -> None:
        """The prompt must work when context is None."""
        prompt = _build_subagent_prompt("Task", None, 3)
        assert "Task" in prompt
        assert "sub-agent" in prompt.lower()


class TestHasPendingToolCalls:
    """Tests for the _has_pending_tool_calls helper."""

    def test_empty_messages(self) -> None:
        """Empty messages list must return False."""
        assert _has_pending_tool_calls([]) is False

    def test_no_tool_calls(self) -> None:
        """A regular assistant message without tool_calls must return False."""
        messages = [{"role": "assistant", "content": "Hello"}]
        assert _has_pending_tool_calls(messages) is False

    def test_unanswered_tool_call(self) -> None:
        """An assistant message with unanswered tool_calls must return True."""
        messages = [
            {
                "role": "assistant",
                "content": "Let me use a tool.",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
            },
        ]
        assert _has_pending_tool_calls(messages) is True

    def test_answered_tool_call(self) -> None:
        """An assistant message with answered tool_calls must return False."""
        messages = [
            {
                "role": "assistant",
                "content": "Let me use a tool.",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
        ]
        assert _has_pending_tool_calls(messages) is False


class TestDelegateExecution:
    """Tests for the delegate function execution."""

    @pytest.mark.asyncio
    async def test_empty_task_raises_error(self) -> None:
        """Calling delegate with an empty task must raise ValueError."""
        from tools.delegate_tool import delegate
        with pytest.raises(ValueError, match="task is required"):
            await delegate("")

    @pytest.mark.asyncio
    async def test_whitespace_task_raises_error(self) -> None:
        """Calling delegate with whitespace-only task must raise ValueError."""
        from tools.delegate_tool import delegate
        with pytest.raises(ValueError, match="task is required"):
            await delegate("   ")
