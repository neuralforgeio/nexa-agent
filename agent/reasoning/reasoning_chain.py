"""
OpenForge — Reasoning Chain
============================

Produces a structured step-by-step reasoning trace the agent can emit
*before* its final answer. Structured reasoning helps the LLM stay
on-track and makes the agent's logic transparent to the user.

A reasoning chain is a list of :class:`ReasoningStep` items, each with:
    - ``thought``   — the reasoning at this step.
    - ``action``    — optional tool/action taken (e.g. ``"search: X"``).
    - ``observation``— optional result of the action.
    - ``confidence``— step-level confidence (0.0–1.0).

The chain is built incrementally and rendered as a single text block
for the system prompt.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReasoningStep:
    """
    One step in a reasoning chain.

    Attributes:
        thought:     The reasoning at this step.
        action:      Optional action taken (e.g. ``"web_search: 'X'"``).
        observation: Optional result of the action.
        confidence:   Step-level confidence (0.0–1.0).
    """

    thought: str
    action: str = ""
    observation: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
            "confidence": self.confidence,
        }


class ReasoningChain:
    """
    Incremental builder for a reasoning chain.
    """

    def __init__(self) -> None:
        self._steps: List[ReasoningStep] = []

    def think(self, thought: str, confidence: float = 1.0) -> "ReasoningChain":
        """
        Add a pure-thought step.

        Args:
            thought:    The reasoning text.
            confidence: Step confidence.

        Returns:
            ``self`` for chaining.
        """
        self._steps.append(ReasoningStep(thought=thought, confidence=confidence))
        return self

    def act(self, thought: str, action: str, observation: str = "", confidence: float = 1.0) -> "ReasoningChain":
        """
        Add a thought + action + observation step.

        Args:
            thought:     Reasoning that led to the action.
            action:      The action taken (e.g. ``"web_search: 'X'"``).
            observation: Result of the action.
            confidence:  Step confidence.

        Returns:
            ``self`` for chaining.
        """
        self._steps.append(
            ReasoningStep(
                thought=thought,
                action=action,
                observation=observation,
                confidence=confidence,
            )
        )
        return self

    def steps(self) -> List[ReasoningStep]:
        """Return the current steps."""
        return list(self._steps)

    def render(self, max_steps: int = 8) -> str:
        """
        Render the chain as a text block for the system prompt.

        Args:
            max_steps: Maximum steps to render.

        Returns:
            A formatted string, or ``""`` if empty.
        """
        if not self._steps:
            return ""
        lines: List[str] = ["Reasoning chain:"]
        for i, step in enumerate(self._steps[:max_steps], 1):
            lines.append(f"{i}. {step.thought}")
            if step.action:
                lines.append(f"   → action: {step.action}")
            if step.observation:
                lines.append(f"   → observation: {step.observation}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the whole chain to a dict."""
        return {"steps": [s.to_dict() for s in self._steps]}

    def __len__(self) -> int:
        return len(self._steps)


def quick_chain(thoughts: List[str]) -> ReasoningChain:
    """
    Build a chain from a list of pure thoughts.

    Args:
        thoughts: List of thought strings.

    Returns:
        A :class:`ReasoningChain`.
    """
    chain = ReasoningChain()
    for t in thoughts:
        chain.think(t)
    return chain
