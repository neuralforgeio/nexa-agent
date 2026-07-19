"""
Nexa Agent — Prompt Expander
============================

Short, vague user messages are hard for an LLM to answer well. This module
**expands** terse messages into rich, structured context that the LLM can
digest faster and more accurately — without changing the user's intent.

Example:
    User says:  "fix it"
    Expander produces a structured block that adds:
        - Detected intent (bug fix request).
        - Inferred subject (the last discussed file/topic).
        - Constraints (don't break existing tests).
        - Suggested approach (read → diagnose → patch → verify).

The expander is **pure-Python** (no LLM call) so it is fast and cheap.
It uses heuristic rules + the conversation history to add context.

Two operating modes:
    1. ``expand_prompt``        — expand a user message in-place.
    2. ``expand_for_llm``       — return a structured dict the agent loop
                                  can inject into the system prompt.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Intent taxonomy
# ---------------------------------------------------------------------------
INTENT_CODE_FIX = "code_fix"
INTENT_EXPLAIN = "explain"
INTENT_GENERATE = "generate"
INTENT_SEARCH = "search"
INTENT_REFACTOR = "refactor"
INTENT_QUESTION = "question"
INTENT_CHAT = "chat"

# Keyword → intent mapping (checked in order; first match wins).
INTENT_RULES: List[tuple] = [
    (re.compile(r"\b(fix|bug|error|broken|crash|fail|traceback|exception)\b", re.I), INTENT_CODE_FIX),
    (re.compile(r"\b(explain|what is|what does|how does|why does|meaning)\b", re.I), INTENT_EXPLAIN),
    (re.compile(r"\b(generate|create|make|build|write|implement|add)\b", re.I), INTENT_GENERATE),
    (re.compile(r"\b(search|find|look up|google|latest|news)\b", re.I), INTENT_SEARCH),
    (re.compile(r"\b(refactor|clean|optimize|simplify|restructure)\b", re.I), INTENT_REFACTOR),
    (re.compile(r"\?", re.I), INTENT_QUESTION),
]

# Very short messages that are almost certainly follow-ups to prior context.
TERSE_FOLLOWUPS = {
    "fix it": "Apply the most likely fix to the last discussed item.",
    "do it": "Proceed with the last suggested action.",
    "yes": "Confirm and continue.",
    "no": "Decline and offer an alternative.",
    "again": "Repeat the last operation.",
    "more": "Provide more detail on the last response.",
    "continue": "Continue from where the last response stopped.",
    "next": "Move to the next step or item.",
    "ok": "Acknowledge and proceed.",
    "go": "Execute the proposed plan.",
}


@dataclass
class ExpandedPrompt:
    """
    The structured result of expanding a user message.

    Attributes:
        original:      The raw user message.
        intent:        Detected intent label.
        subject:       Inferred subject (file, function, topic).
        constraints:   Suggested constraints for the LLM.
        approach:      Suggested step-by-step approach.
        context_hints: Hints drawn from conversation history.
        expanded:      The fully-expanded prompt text (for the LLM).
    """

    original: str
    intent: str = INTENT_CHAT
    subject: str = ""
    constraints: List[str] = field(default_factory=list)
    approach: List[str] = field(default_factory=list)
    context_hints: List[str] = field(default_factory=list)
    expanded: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "original": self.original,
            "intent": self.intent,
            "subject": self.subject,
            "constraints": self.constraints,
            "approach": self.approach,
            "context_hints": self.context_hints,
            "expanded": self.expanded,
        }


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------
def detect_intent(message: str) -> str:
    """
    Classify the user's message into one of the known intent labels.

    Args:
        message: The raw user message.

    Returns:
        An intent label (defaults to :data:`INTENT_CHAT` if no rule matches).
    """
    for pattern, intent in INTENT_RULES:
        if pattern.search(message):
            return intent
    return INTENT_CHAT


# ---------------------------------------------------------------------------
# Subject inference
# ---------------------------------------------------------------------------
# Patterns for common code references.
_FILE_PATTERN = re.compile(r"\b([\w./\\-]+\.(?:py|js|ts|tsx|jsx|md|json|yaml|yml|toml|txt))\b")
_FUNC_PATTERN = re.compile(r"\b(?:function|def|class|method)\s+(\w+)")
_TICK_PATTERN = re.compile(r"`([^`]+)`")
_QUOTED_PATTERN = re.compile(r"[\"']([^\"']{1,80})[\"']")


def infer_subject(message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Infer the subject (file, function, or topic) of the message.

    Looks for explicit file/function references first, then falls back to
    the most recently mentioned file in the conversation history.

    Args:
        message: The raw user message.
        history: Optional list of ``{role, content}`` dicts (newest last).

    Returns:
        The inferred subject string (may be empty).
    """
    m = _FILE_PATTERN.search(message)
    if m:
        return m.group(1)

    m = _FUNC_PATTERN.search(message)
    if m:
        return m.group(1)

    m = _TICK_PATTERN.search(message)
    if m:
        return m.group(1)

    m = _QUOTED_PATTERN.search(message)
    if m:
        return m.group(1)

    # Fallback: scan history for the last file mention.
    if history:
        for msg in reversed(history):
            content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            m = _FILE_PATTERN.search(content)
            if m:
                return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# Constraint + approach suggestion
# ---------------------------------------------------------------------------
def suggest_constraints(intent: str) -> List[str]:
    """Return suggested constraints for the given intent."""
    table: Dict[str, List[str]] = {
        INTENT_CODE_FIX: [
            "Do not break existing tests.",
            "Preserve the public API surface.",
            "Add or update a test that reproduces the bug.",
        ],
        INTENT_GENERATE: [
            "Follow existing code style and naming conventions.",
            "Add docstrings with Args/Returns/Raises.",
            "Include a usage example.",
        ],
        INTENT_REFACTOR: [
            "Behavior must be identical before and after.",
            "Keep the diff minimal.",
            "Run tests to confirm no regressions.",
        ],
        INTENT_EXPLAIN: [
            "Be concise but complete.",
            "Use a concrete code example if helpful.",
        ],
        INTENT_SEARCH: [
            "Cite sources with URLs.",
            "Prefer primary sources over secondary.",
        ],
    }
    return table.get(intent, [])


def suggest_approach(intent: str, subject: str = "") -> List[str]:
    """Return a suggested step-by-step approach for the intent."""
    subj = f" `{subject}`" if subject else ""
    table: Dict[str, List[str]] = {
        INTENT_CODE_FIX: [
            f"Read{subj} to understand the current behavior.",
            "Identify the root cause of the reported symptom.",
            "Apply the minimal fix.",
            "Run the relevant tests.",
        ],
        INTENT_GENERATE: [
            f"Confirm the target location for{subj}.",
            "Write the implementation with type hints.",
            "Write a unit test.",
            "Run the test to verify.",
        ],
        INTENT_REFACTOR: [
            f"Read{subj} fully.",
            "Identify the smell or duplication.",
            "Apply the refactor in small steps.",
            "Verify behavior with tests.",
        ],
        INTENT_EXPLAIN: [
            f"Locate{subj} in the codebase.",
            "Summarize what it does and why.",
            "Point out non-obvious details.",
        ],
        INTENT_SEARCH: [
            "Formulate a precise search query.",
            "Run the web_search tool.",
            "Synthesize the answer with citations.",
        ],
    }
    return table.get(intent, [])


# ---------------------------------------------------------------------------
# History hint extraction
# ---------------------------------------------------------------------------
def extract_context_hints(history: Optional[List[Dict[str, str]]]) -> List[str]:
    """
    Pull lightweight context hints from recent history.

    Args:
        history: Conversation history (newest last). Only the last 6 messages
                 are considered to keep this cheap.

    Returns:
        A list of short hint strings.
    """
    if not history:
        return []
    hints: List[str] = []
    for msg in history[-6:]:
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        role = msg.get("role", "user") if isinstance(msg, dict) else "user"
        # Mention files seen recently.
        for m in _FILE_PATTERN.finditer(content):
            hint = f"Recent file mentioned: {m.group(1)}"
            if hint not in hints:
                hints.append(hint)
        # Mention errors seen recently.
        if role == "assistant" and "error" in content.lower():
            hints.append("A prior error was discussed; consider it relevant.")
    return hints[:5]


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------
def expand_prompt(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> ExpandedPrompt:
    """
    Expand a terse user message into a rich, structured prompt.

    The expansion adds detected intent, inferred subject, suggested
    constraints, a step-by-step approach, and lightweight context hints
    — all without changing the user's original intent.

    Args:
        message: The raw user message.
        history: Optional conversation history (newest last).

    Returns:
        An :class:`ExpandedPrompt` with the full structured expansion.
    """
    original = message.strip()
    intent = detect_intent(original)
    subject = infer_subject(original, history)
    constraints = suggest_constraints(intent)
    approach = suggest_approach(intent, subject)
    context_hints = extract_context_hints(history)

    # Special-case: very terse follow-ups get an explicit nudge.
    terse = TERSE_FOLLOWUPS.get(original.lower())
    if terse and not subject:
        context_hints.insert(0, terse)

    # Build the expanded prompt text.
    sections: List[str] = [f"[User message]: {original}"]
    sections.append(f"[Detected intent]: {intent}")
    if subject:
        sections.append(f"[Inferred subject]: {subject}")
    if context_hints:
        sections.append("[Context hints]:")
        for h in context_hints:
            sections.append(f"  - {h}")
    if constraints:
        sections.append("[Constraints]:")
        for c in constraints:
            sections.append(f"  - {c}")
    if approach:
        sections.append("[Suggested approach]:")
        for i, step in enumerate(approach, 1):
            sections.append(f"  {i}. {step}")
    sections.append(
        "[Instruction]: Use the above context to produce a focused, accurate response. "
        "Do not mention these scaffolding notes to the user."
    )

    expanded = "\n".join(sections)
    return ExpandedPrompt(
        original=original,
        intent=intent,
        subject=subject,
        constraints=constraints,
        approach=approach,
        context_hints=context_hints,
        expanded=expanded,
    )


def expand_for_llm(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Return the expansion as a dict for injection into the system prompt.

    Convenience wrapper around :func:`expand_prompt` returning a plain dict.

    Args:
        message: The raw user message.
        history: Optional conversation history.

    Returns:
        The :meth:`ExpandedPrompt.to_dict` result.
    """
    return expand_prompt(message, history).to_dict()


def should_expand(message: str) -> bool:
    """
    Decide whether a message is terse enough to warrant expansion.

    Returns ``True`` if the message is short (≤ 12 words) or matches a
    known terse follow-up. Long, detailed messages are passed through.

    Args:
        message: The raw user message.

    Returns:
        ``True`` if expansion is recommended.
    """
    stripped = message.strip()
    if not stripped:
        return False
    if stripped.lower() in TERSE_FOLLOWUPS:
        return True
    word_count = len(stripped.split())
    return word_count <= 12
