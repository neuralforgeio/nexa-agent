"""
OpenForge — Intent Classifier
==============================

A richer intent classifier than the one in :mod:`agent.prompt_expander`.
This one produces a structured intent object with sub-type, expected
output format, and suggested tools — so the conversation loop can
pre-warm the right tools and tailor the system prompt.

Intent taxonomy:
    - code_help     (write/fix/refactor code)
    - factual_qa    (ask for a fact)
    - how_to        (ask for steps)
    - opinion       (ask for recommendation)
    - conversation  (chit-chat)
    - meta          (about the agent itself: /help, status)

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Primary intent labels.
INTENT_CODE_HELP = "code_help"
INTENT_FACTUAL_QA = "factual_qa"
INTENT_HOW_TO = "how_to"
INTENT_OPINION = "opinion"
INTENT_CONVERSATION = "conversation"
INTENT_META = "meta"

# Suggested tool sets per intent.
INTENT_TOOLS: Dict[str, List[str]] = {
    INTENT_CODE_HELP: ["read_file", "write_file", "code_execution", "file_patch"],
    INTENT_FACTUAL_QA: ["web_search"],
    INTENT_HOW_TO: ["web_search", "read_file"],
    INTENT_OPINION: [],
    INTENT_CONVERSATION: [],
    INTENT_META: [],
}

# Expected output formats per intent.
INTENT_FORMATS: Dict[str, str] = {
    INTENT_CODE_HELP: "code block + explanation",
    INTENT_FACTUAL_QA: "short answer + source",
    INTENT_HOW_TO: "numbered steps",
    INTENT_OPINION: "recommendation + trade-offs",
    INTENT_CONVERSATION: "natural prose",
    INTENT_META: "concise status reply",
}

# Rules (checked in order; first match wins).
RULES: List[tuple] = [
    (re.compile(r"\b(help|about|what can you|who are you|your (name|version)|/help)\b", re.I), INTENT_META),
    (re.compile(r"\b(fix|bug|error|refactor|implement|write|build|code|function|class|test)\b", re.I), INTENT_CODE_HELP),
    (re.compile(r"\bhow (do|to|can|does)\b|\bsteps?\b|\bguid", re.I), INTENT_HOW_TO),
    (re.compile(r"\b(should i|which is better|recommend|best|vs\.?)\b", re.I), INTENT_OPINION),
    (re.compile(r"\b(what is|who is|when did|where is|why is|how many|how much)\b", re.I), INTENT_FACTUAL_QA),
]


@dataclass
class Intent:
    """
    A classified user intent.

    Attributes:
        label:          Primary intent label.
        sub_type:       Optional sub-type (e.g. ``"python"`` for code_help).
        suggested_tools:Tools the agent might pre-warm.
        output_format:  Expected answer format.
        confidence:     Heuristic confidence (0.0–1.0).
    """

    label: str
    sub_type: str = ""
    suggested_tools: List[str] = field(default_factory=list)
    output_format: str = ""
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "label": self.label,
            "sub_type": self.sub_type,
            "suggested_tools": self.suggested_tools,
            "output_format": self.output_format,
            "confidence": self.confidence,
        }


def classify_intent(message: str) -> Intent:
    """
    Classify a user message into an :class:`Intent`.

    Args:
        message: The raw user message.

    Returns:
        An :class:`Intent`. Defaults to :data:`INTENT_CONVERSATION`.
    """
    for pattern, label in RULES:
        if pattern.search(message):
            sub = _detect_sub_type(message, label)
            return Intent(
                label=label,
                sub_type=sub,
                suggested_tools=INTENT_TOOLS.get(label, []),
                output_format=INTENT_FORMATS.get(label, ""),
                confidence=0.75,
            )
    return Intent(
        label=INTENT_CONVERSATION,
        suggested_tools=INTENT_TOOLS[INTENT_CONVERSATION],
        output_format=INTENT_FORMATS[INTENT_CONVERSATION],
        confidence=0.4,
    )


def _detect_sub_type(message: str, label: str) -> str:
    """Detect a sub-type (e.g. programming language for code_help)."""
    if label == INTENT_CODE_HELP:
        m = re.search(r"\b(python|javascript|typescript|rust|go|java|c\+\+|sql)\b", message, re.I)
        if m:
            return m.group(1).lower()
    if label == INTENT_FACTUAL_QA:
        m = re.search(r"\b(person|place|date|year|company|country|city)\b", message, re.I)
        if m:
            return m.group(1).lower()
    return ""


def intent_block(intent: Intent) -> str:
    """
    Build a short system-prompt block describing the detected intent.

    Args:
        intent: The classified intent.

    Returns:
        A formatted string suitable for the system prompt.
    """
    lines: List[str] = [f"Detected user intent: {intent.label}"]
    if intent.sub_type:
        lines.append(f"Sub-type: {intent.sub_type}")
    if intent.suggested_tools:
        lines.append(f"Likely-useful tools: {', '.join(intent.suggested_tools)}")
    if intent.output_format:
        lines.append(f"Preferred answer format: {intent.output_format}")
    return "\n".join(lines)
