"""
Nexa Agent — Prompt Builder
===========================

Assembles the system prompt dynamically from multiple context sources:

    - Agent identity (name, version, tagline, author).
    - Active tool catalog with usage guidance from the learning graph.
    - Long-term memory digest (DB memories + MEMORY.md file).
    - User profile from USER.md (preferences, facts about the user).
    - Conversation context summary (if available).
    - Provider-specific hints (model capabilities, token budget).

The prompt is structured into clearly delimited sections so the LLM can
parse and reference them efficiently. Each section uses Markdown-style
headers for hierarchical organization.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from nexa.constants import NEXA_AUTHOR, NEXA_NAME, NEXA_TAGLINE, NEXA_VERSION

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


def build_system_prompt(
    registry: "ToolRegistry",
    memory_digest: str = "",
    user_profile: str = "",
    context_summary: str = "",
    learning_stats: Optional[Dict[str, Any]] = None,
    provider_hint: str = "",
) -> str:
    """
    Build a comprehensive system prompt for the agent.

    The prompt is assembled from multiple sections, each providing
    context that helps the agent respond intelligently:

    1. **Identity** — Who the agent is, its version, and capabilities.
    2. **Behavioral Guidelines** — How the agent should reason and act.
    3. **Tool Catalog** — Available tools with descriptions and usage tips.
    4. **Learning Insights** — Tool success rates from past usage.
    5. **User Profile** — Known preferences and facts about the user.
    6. **Memory Digest** — Accumulated knowledge from past conversations.
    7. **Context Summary** — Summary of the current conversation so far.
    8. **Provider Hints** — Model-specific guidance (if applicable).

    Args:
        registry:        The tool registry (to list available tools).
        memory_digest:   A memory summary string from the memory curator.
        user_profile:    The user profile text (from USER.md or DB).
        context_summary: A summary of the conversation so far (from
                         context compression, if triggered).
        learning_stats:  Optional dict with tool success/failure stats
                         from the learning graph.
        provider_hint:   Optional model-specific guidance string.

    Returns:
        The full system prompt as a single string with newline separators.
    """
    sections: List[str] = []

    # --- Section 1: Identity ---
    sections.append(_build_identity_section())

    # --- Section 2: Behavioral Guidelines ---
    sections.append(_build_behavior_section())

    # --- Section 3: Tool Catalog ---
    sections.append(_build_tools_section(registry))

    # --- Section 4: Learning Insights ---
    if learning_stats:
        insights = _build_learning_section(learning_stats)
        if insights:
            sections.append(insights)

    # --- Section 5: User Profile ---
    if user_profile and user_profile.strip():
        sections.append(_build_user_profile_section(user_profile))

    # --- Section 6: Memory Digest ---
    if memory_digest and memory_digest.strip():
        sections.append(_build_memory_section(memory_digest))

    # --- Section 7: Context Summary ---
    if context_summary and context_summary.strip():
        sections.append(_build_context_section(context_summary))

    # --- Section 8: Provider Hints ---
    if provider_hint and provider_hint.strip():
        sections.append(_build_provider_section(provider_hint))

    return "\n\n".join(sections)


def _build_identity_section() -> str:
    """
    Build the agent identity section.

    Returns:
        A formatted string with the agent's name, version, tagline,
        and author.
    """
    return "\n".join(
        [
            "# Agent Identity",
            f"You are **{NEXA_NAME}** v{NEXA_VERSION}.",
            f"{NEXA_TAGLINE}.",
            f"Created by {NEXA_AUTHOR}.",
        ]
    )


def _build_behavior_section() -> str:
    """
    Build the behavioral guidelines section.

    This section instructs the agent on how to reason, when to use tools,
    and how to format responses.

    Returns:
        A formatted string with behavioral guidelines.
    """
    return "\n".join(
        [
            "# Behavioral Guidelines",
            "1. **Reason step by step** — Think through problems methodically.",
            "2. **Use tools when needed** — Call tools via the function-calling",
            "   interface to ground your answers in real data.",
            "3. **One tool per turn** — Call at most one tool, then wait for",
            "   the result before continuing.",
            "4. **Be concise** — Avoid unnecessary verbosity. Get to the point.",
            "5. **Be accurate** — If you're unsure, say so. Don't fabricate.",
            "6. **Be helpful** — Anticipate follow-up needs and offer guidance.",
            "7. **Respect user preferences** — Follow the user's stated preferences",
            "   for response style, language, and detail level.",
            "8. **Acknowledge uncertainty** — If a tool fails or data is missing,",
            "   explain what happened and suggest alternatives.",
        ]
    )


def _build_tools_section(registry: "ToolRegistry") -> str:
    """
    Build the tool catalog section.

    Args:
        registry: The tool registry with registered tools.

    Returns:
        A formatted string listing all available tools with descriptions.
    """
    tool_catalog = registry.describe()
    return "\n".join(
        [
            "# Available Tools",
            "You have access to the following tools. Call them via the",
            "function-calling interface when you need to perform actions.",
            "",
            tool_catalog,
        ]
    )


def _build_learning_section(stats: Dict[str, Any]) -> str:
    """
    Build the learning insights section from learning graph stats.

    This section shows the agent which tools have been successful in the
    past, helping it make better tool selection decisions.

    Args:
        stats: A dict with learning statistics (from
               :meth:`~nexa.state.ConversationDB.get_learning_stats`).

    Returns:
        A formatted string with tool usage insights, or empty string
        if no data is available.
    """
    tool_stats: List[Dict[str, Any]] = stats.get("tool_stats", [])
    if not tool_stats:
        return ""

    lines = [
        "# Learning Insights",
        "Based on past interactions, here are tool success rates:",
        "",
    ]
    for ts in tool_stats[:5]:  # Top 5 tools by usage.
        tool = ts.get("tool", "unknown")
        success = ts.get("success", 0)
        failure = ts.get("failure", 0)
        total = success + failure
        if total > 0:
            rate = (success / total) * 100
            lines.append(f"- **{tool}**: {rate:.0f}% success ({success}✓/{failure}✗)")
        else:
            lines.append(f"- **{tool}**: no data yet")

    lines.append("")
    lines.append("Prefer tools with higher success rates when multiple options exist.")
    return "\n".join(lines)


def _build_user_profile_section(profile: str) -> str:
    """
    Build the user profile section.

    Args:
        profile: The user profile text (from USER.md or DB).

    Returns:
        A formatted string with the user profile.
    """
    return "\n".join(
        [
            "# User Profile",
            "The following is known about the user. Tailor your responses",
            "accordingly:",
            "",
            profile.strip(),
        ]
    )


def _build_memory_section(digest: str) -> str:
    """
    Build the memory digest section.

    Args:
        digest: The memory digest string from the memory curator.

    Returns:
        A formatted string with accumulated memories.
    """
    return "\n".join(
        [
            "# Long-term Memory",
            "The following insights have been accumulated from past conversations.",
            "Use this knowledge to provide better, more personalized responses:",
            "",
            digest.strip(),
        ]
    )


def _build_context_section(summary: str) -> str:
    """
    Build the context summary section.

    This is included when the context compressor has summarized older
    messages to fit the token budget.

    Args:
        summary: The context summary string.

    Returns:
        A formatted string with the conversation summary.
    """
    return "\n".join(
        [
            "# Conversation Summary",
            "Earlier messages in this conversation were summarized to fit",
            "the context window. Here is the summary:",
            "",
            summary.strip(),
        ]
    )


def _build_provider_section(hint: str) -> str:
    """
    Build the provider hints section.

    Args:
        hint: Provider-specific guidance (e.g., model capabilities,
              token limits, special features).

    Returns:
        A formatted string with provider hints.
    """
    return "\n".join(
        [
            "# Provider Information",
            hint.strip(),
        ]
    )
