"""
Tests for :class:`agent.context.context_compressor.ContextCompressor`.

v4.15.1 regression suite — the llama.cpp ``--jinja`` chat template requires
every ``system``-role message to sit at index 0. Compression must therefore
fold the generated context summary INTO the leading system message instead
of inserting a second system message in the middle of the transcript
(which triggers: "Jinja Exception: System message must be at the beginning.").

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest

from agent.context.context_compressor import ContextCompressor


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def _always_over_budget(self, messages) -> bool:  # noqa: ANN001
    return True


@pytest.fixture
def over_budget_compressor(monkeypatch) -> ContextCompressor:
    """A provider-less (truncation) compressor forced to always compress."""
    monkeypatch.setattr(ContextCompressor, "needs_compression", _always_over_budget)
    return ContextCompressor(token_budget=1, provider=None)


@pytest.mark.asyncio
async def test_compress_keeps_single_system_at_index_zero(over_budget_compressor) -> None:
    """Regression (Bug 1 / Jinja): after compression there must be exactly ONE
    ``system`` message and it must sit at index 0. Without the fix, the summary
    was inserted as a NEW system message right after the original one, i.e. at
    index 1 with user/assistant turns after it — llama.cpp rejects that."""
    messages = [_msg("system", "base system prompt.")] + [
        _msg("user" if i % 2 == 0 else "assistant", f"turn {i} content") for i in range(12)
    ]

    compressed, was_compressed = await over_budget_compressor.compress_if_needed(messages)

    assert was_compressed is True
    # Exactly one system message, at index 0. (This assertion FAILS without
    # the v4.15.1 fix, where the summary lands as a system message at idx 1.)
    system_positions = [i for i, m in enumerate(compressed) if m.get("role") == "system"]
    assert system_positions == [0]


@pytest.mark.asyncio
async def test_compress_folds_summary_into_existing_system(over_budget_compressor) -> None:
    """The context summary must be appended INTO the original system prompt
    content rather than becoming a separate message."""
    messages = [_msg("system", "base system prompt.")] + [
        _msg("user", f"question {i}") for i in range(10)
    ]

    compressed, was_compressed = await over_budget_compressor.compress_if_needed(messages)

    assert was_compressed is True
    head = compressed[0]
    assert head["role"] == "system"
    assert "base system prompt." in head["content"]
    assert "[Context Summary]" in head["content"]


@pytest.mark.asyncio
async def test_compress_without_leading_system_still_safe(over_budget_compressor) -> None:
    """When the transcript has NO leading system message (legal but unusual),
    the summary may be a system message — it still sits at index 0."""
    messages = [_msg("user" if i % 2 == 0 else "assistant", f"turn {i}") for i in range(10)]

    compressed, was_compressed = await over_budget_compressor.compress_if_needed(messages)

    assert was_compressed is True
    system_positions = [i for i, m in enumerate(compressed) if m.get("role") == "system"]
    assert system_positions == [0]
    assert "[Context Summary]" in compressed[0]["content"]


@pytest.mark.asyncio
async def test_compress_noop_when_within_budget() -> None:
    """Sanity: a transcript within budget is returned untouched."""
    compressor = ContextCompressor(token_budget=10_000_000, provider=None)
    messages = [_msg("system", "sys"), _msg("user", "hi")]
    compressed, was_compressed = await compressor.compress_if_needed(messages)
    assert was_compressed is False
    assert compressed is messages
