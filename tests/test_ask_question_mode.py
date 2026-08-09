"""
Tests for the Ask Question Mode (v3.1.0).

Verifies:
    - should_use_quick_mode returns True for simple factual questions.
    - should_use_quick_mode returns False for tool-needing messages.
    - should_use_quick_mode respects the ``force`` override.
    - build_quick_system_prompt strips the "# Available Tools" section.
    - is_quick_mode_enabled reads FORGE_QUICK_MODE env.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
import pytest

from agent.prompt.ask_question_mode import (
    build_quick_system_prompt,
    is_quick_mode_enabled,
    should_use_quick_mode,
)


class TestShouldUseQuickMode:
    """Tests for the quick-mode heuristic."""

    def test_simple_factual_question(self) -> None:
        """Short factual questions use quick mode."""
        assert should_use_quick_mode("What is the capital of France?") is True
        assert should_use_quick_mode("Who wrote Hamlet?") is True
        assert should_use_quick_mode("What is 2+2?") is True

    def test_long_message_not_quick(self) -> None:
        """Long messages bypass quick mode."""
        long_msg = " ".join(["word"] * 15)
        assert should_use_quick_mode(long_msg) is False

    def test_action_verbs_not_quick(self) -> None:
        """Messages with action verbs (fix, write, read) bypass quick mode."""
        assert should_use_quick_mode("fix the bug") is False
        assert should_use_quick_mode("read forge-workspace/file.txt") is False
        assert should_use_quick_mode("search the web for AI news") is False
        assert should_use_quick_mode("create a new file") is False

    def test_file_reference_not_quick(self) -> None:
        """Messages with file references bypass quick mode."""
        assert should_use_quick_mode("explain provider.py") is False
        assert should_use_quick_mode("look at config.json") is False

    def test_backtick_code_not_quick(self) -> None:
        """Messages with backtick code references bypass quick mode."""
        assert should_use_quick_mode("explain `read_file` tool") is False

    def test_empty_message_not_quick(self) -> None:
        """Empty messages don't use quick mode."""
        assert should_use_quick_mode("") is False
        assert should_use_quick_mode("   ") is False

    def test_force_override_true(self) -> None:
        """force=True overrides the heuristic."""
        assert should_use_quick_mode("fix the bug", force=True) is True

    def test_force_override_false(self) -> None:
        """force=False overrides the heuristic."""
        assert should_use_quick_mode("What is the capital?", force=False) is False


class TestBuildQuickSystemPrompt:
    """Tests for the system prompt simplifier."""

    def test_strips_available_tools_section(self) -> None:
        """The '# Available Tools' section is removed."""
        prompt = (
            "# Agent Identity\n"
            "You are OpenForge.\n\n"
            "# Available Tools\n"
            "- read_file: read a file\n"
            "- write_file: write a file\n\n"
            "# Behavioral Guidelines\n"
            "Be concise."
        )
        simplified = build_quick_system_prompt(prompt)
        assert "# Available Tools" not in simplified
        assert "# Agent Identity" in simplified
        assert "# Behavioral Guidelines" in simplified

    def test_preserves_other_sections(self) -> None:
        """Non-tool sections are preserved."""
        prompt = (
            "# Identity\nOpenForge\n\n"
            "# Available Tools\n- read_file\n\n"
            "# Memory\nUser prefers Python."
        )
        simplified = build_quick_system_prompt(prompt)
        assert "# Identity" in simplified
        assert "# Memory" in simplified
        assert "User prefers Python" in simplified

    def test_no_tools_section_returns_unchanged(self) -> None:
        """If there's no tools section, the prompt is unchanged (except whitespace)."""
        prompt = "# Identity\nOpenForge\n\n# Memory\nUser prefers Python."
        simplified = build_quick_system_prompt(prompt)
        assert "Forge" in simplified
        assert "User prefers Python" in simplified


class TestIsQuickModeEnabled:
    """Tests for the env-var check."""

    def test_default_off(self, monkeypatch) -> None:
        """Quick mode is off by default."""
        monkeypatch.delenv("FORGE_QUICK_MODE", raising=False)
        assert is_quick_mode_enabled() is False

    def test_enabled_when_set(self, monkeypatch) -> None:
        """FORGE_QUICK_MODE=1 enables it."""
        monkeypatch.setenv("FORGE_QUICK_MODE", "1")
        assert is_quick_mode_enabled() is True

    def test_enabled_when_true(self, monkeypatch) -> None:
        """FORGE_QUICK_MODE=true enables it."""
        monkeypatch.setenv("FORGE_QUICK_MODE", "true")
        assert is_quick_mode_enabled() is True

    def test_disabled_when_zero(self, monkeypatch) -> None:
        """FORGE_QUICK_MODE=0 disables it."""
        monkeypatch.setenv("FORGE_QUICK_MODE", "0")
        assert is_quick_mode_enabled() is False
