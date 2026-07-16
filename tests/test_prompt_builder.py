"""
Tests for the prompt builder module.

Verifies:
    - build_system_prompt produces all expected sections.
    - Each section contains correct content.
    - Optional sections are omitted when not provided.
    - The identity section includes name, version, tagline, author.
    - The behavioral guidelines section has numbered rules.
    - The tools section lists all registered tools.
    - The learning insights section formats success rates correctly.
    - The user profile section includes the profile text.
    - The memory section includes the digest.
    - The context summary section includes the summary.
    - The provider section includes the hint.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest

from agent.prompt_builder import (
    build_system_prompt,
    _build_identity_section,
    _build_behavior_section,
    _build_tools_section,
    _build_learning_section,
    _build_user_profile_section,
    _build_memory_section,
    _build_context_section,
    _build_provider_section,
)
from tools.registry import create_default_registry


@pytest.fixture
def registry():
    """Provide a default tool registry for tests."""
    return create_default_registry()


class TestBuildSystemPrompt:
    """Tests for the main build_system_prompt function."""

    def test_returns_non_empty_string(self, registry) -> None:
        """The prompt must be a non-empty string."""
        prompt = build_system_prompt(registry)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_includes_identity_section(self, registry) -> None:
        """The prompt must include the agent identity."""
        prompt = build_system_prompt(registry)
        assert "Nexa Agent" in prompt
        assert "v1.3.0" in prompt or "v1." in prompt  # Version is present.

    def test_includes_behavior_section(self, registry) -> None:
        """The prompt must include behavioral guidelines."""
        prompt = build_system_prompt(registry)
        assert "Behavioral Guidelines" in prompt
        assert "step by step" in prompt.lower()

    def test_includes_tools_section(self, registry) -> None:
        """The prompt must list available tools."""
        prompt = build_system_prompt(registry)
        assert "Available Tools" in prompt
        assert "read_file" in prompt
        assert "write_file" in prompt
        assert "delegate" in prompt

    def test_includes_memory_when_provided(self, registry) -> None:
        """The prompt must include memory digest when provided."""
        prompt = build_system_prompt(registry, memory_digest="User prefers Python")
        assert "Long-term Memory" in prompt
        assert "User prefers Python" in prompt

    def test_omits_memory_when_empty(self, registry) -> None:
        """The prompt must omit memory section when digest is empty."""
        prompt = build_system_prompt(registry, memory_digest="")
        assert "Long-term Memory" not in prompt

    def test_includes_user_profile_when_provided(self, registry) -> None:
        """The prompt must include user profile when provided."""
        prompt = build_system_prompt(registry, user_profile="Name: Dearly")
        assert "User Profile" in prompt
        assert "Name: Dearly" in prompt

    def test_omits_user_profile_when_empty(self, registry) -> None:
        """The prompt must omit user profile when empty."""
        prompt = build_system_prompt(registry, user_profile="")
        assert "User Profile" not in prompt

    def test_includes_learning_stats_when_provided(self, registry) -> None:
        """The prompt must include learning insights when stats are provided."""
        stats = {
            "tool_stats": [
                {"tool": "read_file", "success": 8, "failure": 2},
                {"tool": "write_file", "success": 5, "failure": 1},
            ]
        }
        prompt = build_system_prompt(registry, learning_stats=stats)
        assert "Learning Insights" in prompt
        assert "read_file" in prompt
        assert "80%" in prompt  # 8/10 = 80%

    def test_omits_learning_when_no_stats(self, registry) -> None:
        """The prompt must omit learning section when stats are empty."""
        prompt = build_system_prompt(registry, learning_stats={})
        assert "Learning Insights" not in prompt

    def test_includes_context_summary_when_provided(self, registry) -> None:
        """The prompt must include context summary when provided."""
        prompt = build_system_prompt(registry, context_summary="User asked about files")
        assert "Conversation Summary" in prompt
        assert "User asked about files" in prompt

    def test_includes_provider_hint_when_provided(self, registry) -> None:
        """The prompt must include provider hints when provided."""
        prompt = build_system_prompt(registry, provider_hint="Model: GPT-4o, 128K context")
        assert "Provider Information" in prompt
        assert "GPT-4o" in prompt

    def test_all_sections_together(self, registry) -> None:
        """All sections must be present when all arguments are provided."""
        prompt = build_system_prompt(
            registry,
            memory_digest="Some memory",
            user_profile="Some profile",
            context_summary="Some summary",
            learning_stats={"tool_stats": [{"tool": "test", "success": 1, "failure": 0}]},
            provider_hint="Some hint",
        )
        assert "Agent Identity" in prompt
        assert "Behavioral Guidelines" in prompt
        assert "Available Tools" in prompt
        assert "Learning Insights" in prompt
        assert "User Profile" in prompt
        assert "Long-term Memory" in prompt
        assert "Conversation Summary" in prompt
        assert "Provider Information" in prompt


class TestIdentitySection:
    """Tests for the _build_identity_section function."""

    def test_includes_name(self) -> None:
        """The identity must include the agent name."""
        section = _build_identity_section()
        assert "Nexa Agent" in section

    def test_includes_version(self) -> None:
        """The identity must include the version."""
        section = _build_identity_section()
        assert "v1." in section

    def test_includes_author(self) -> None:
        """The identity must include the author."""
        section = _build_identity_section()
        assert "Dearly Febriano Irwansyah" in section


class TestBehaviorSection:
    """Tests for the _build_behavior_section function."""

    def test_has_numbered_guidelines(self) -> None:
        """The behavior section must have numbered rules."""
        section = _build_behavior_section()
        assert "1." in section
        assert "2." in section

    def test_mentions_tools(self) -> None:
        """The behavior section must mention tool usage."""
        section = _build_behavior_section()
        assert "tool" in section.lower()


class TestToolsSection:
    """Tests for the _build_tools_section function."""

    def test_lists_all_tools(self, registry) -> None:
        """The tools section must list all registered tools."""
        section = _build_tools_section(registry)
        for tool_name in registry.list_names():
            assert tool_name in section


class TestLearningSection:
    """Tests for the _build_learning_section function."""

    def test_formats_success_rate(self) -> None:
        """The learning section must format success rates as percentages."""
        stats = {"tool_stats": [{"tool": "read_file", "success": 7, "failure": 3}]}
        section = _build_learning_section(stats)
        assert "70%" in section  # 7/10 = 70%

    def test_returns_empty_for_no_data(self) -> None:
        """The learning section must return empty string when no data."""
        section = _build_learning_section({"tool_stats": []})
        assert section == ""

    def test_includes_tool_name(self) -> None:
        """The learning section must include tool names."""
        stats = {"tool_stats": [{"tool": "write_file", "success": 1, "failure": 0}]}
        section = _build_learning_section(stats)
        assert "write_file" in section


class TestUserProfileSection:
    """Tests for the _build_user_profile_section function."""

    def test_includes_profile_text(self) -> None:
        """The section must include the profile text."""
        section = _build_user_profile_section("Likes Python")
        assert "Likes Python" in section

    def test_strips_whitespace(self) -> None:
        """The section must strip whitespace from the profile."""
        section = _build_user_profile_section("  spaced  ")
        assert "spaced" in section
        assert "  spaced  " not in section


class TestMemorySection:
    """Tests for the _build_memory_section function."""

    def test_includes_digest(self) -> None:
        """The section must include the memory digest."""
        section = _build_memory_section("Some insight about Python")
        assert "Some insight about Python" in section


class TestContextSection:
    """Tests for the _build_context_section function."""

    def test_includes_summary(self) -> None:
        """The section must include the context summary."""
        section = _build_context_section("User discussed file operations")
        assert "User discussed file operations" in section


class TestProviderSection:
    """Tests for the _build_provider_section function."""

    def test_includes_hint(self) -> None:
        """The section must include the provider hint."""
        section = _build_provider_section("Model supports 128K tokens")
        assert "Model supports 128K tokens" in section
