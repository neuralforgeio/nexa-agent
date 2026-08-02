"""
Nexa Agent — Adaptive Persona
============================

Adjusts the agent's tone, verbosity, and formality to match the user's
apparent preference, inferred from their message style. This makes the
agent feel more natural without any explicit "personality" config.

Dimensions adapted:
    - Formality:   formal vs casual.
    - Verbosity:   concise vs verbose.
    - Tone:        neutral vs friendly vs technical.

The persona is updated after every user message and surfaced in the
system prompt via :func:`persona_block`.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

# Formality signals.
FORMAL_MARKERS = ("please", "kindly", "would you", "could you", "thank you", "regards")
CASUAL_MARKERS = ("hey", "hi", "yo", "sup", "thanks", "cheers", "lol", "btw", "ok")

# Verbosity signals.
VERBOSE_MARKERS = ("please", "in detail", "step by step", "thorough", "comprehensive", "elaborate")
CONCISE_MARKERS = ("briefly", "short", "tldr", "tl;dr", "quick", "summary", "one line")

# Tone signals.
TECHNICAL_MARKERS = ("code", "function", "api", "schema", "deploy", "compiler", "runtime")


@dataclass
class Persona:
    """
    The agent's current persona settings.

    Attributes:
        formality:   0.0 (casual) … 1.0 (formal). Default 0.5 (neutral).
        verbosity:   0.0 (concise) … 1.0 (verbose). Default 0.5.
        tone:        One of "neutral", "friendly", "technical".
        samples:     Number of user messages observed.
    """

    formality: float = 0.5
    verbosity: float = 0.5
    tone: str = "neutral"
    samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "formality": round(self.formality, 2),
            "verbosity": round(self.verbosity, 2),
            "tone": self.tone,
            "samples": self.samples,
        }


class AdaptivePersona:
    """
    Stateful persona adapter.

    Call :meth:`observe` for every user message to update the persona,
    then :meth:`persona` to read the current state.
    """

    def __init__(self, smoothing: float = 0.3) -> None:
        """
        Initialize with a neutral persona.

        Args:
            smoothing: Exponential moving average factor (0–1). Lower =
                       more conservative (slower to change).
        """
        self._persona = Persona()
        self._smoothing = smoothing

    def observe(self, message: str) -> Persona:
        """
        Update the persona based on a new user message.

        Args:
            message: The raw user message.

        Returns:
            The updated :class:`Persona`.
        """
        msg_lower = message.lower()
        self._persona.samples += 1

        # Formality.
        formal_hits = sum(1 for m in FORMAL_MARKERS if m in msg_lower)
        casual_hits = sum(1 for m in CASUAL_MARKERS if m in msg_lower)
        if formal_hits or casual_hits:
            target = 0.5 + 0.15 * (formal_hits - casual_hits)
            target = max(0.0, min(1.0, target))
            self._ema("formality", target)

        # Verbosity.
        verbose_hits = sum(1 for m in VERBOSE_MARKERS if m in msg_lower)
        concise_hits = sum(1 for m in CONCISE_MARKERS if m in msg_lower)
        if verbose_hits or concise_hits:
            target = 0.5 + 0.2 * (verbose_hits - concise_hits)
            target = max(0.0, min(1.0, target))
            self._ema("verbosity", target)
        # Also factor the message length.
        word_count = len(message.split())
        if word_count > 30:
            self._ema("verbosity", min(1.0, self._persona.verbosity + 0.1))
        elif word_count < 5:
            self._ema("verbosity", max(0.0, self._persona.verbosity - 0.1))

        # Tone.
        tech_hits = sum(1 for m in TECHNICAL_MARKERS if m in msg_lower)
        friendly_hits = sum(1 for m in CASUAL_MARKERS if m in msg_lower)
        if tech_hits > friendly_hits:
            self._persona.tone = "technical"
        elif friendly_hits > tech_hits:
            self._persona.tone = "friendly"
        # Else: keep current tone (don't flip-flop).

        return self._persona

    def _ema(self, attr: str, target: float) -> None:
        """Exponential moving average update on a persona attribute."""
        current = getattr(self._persona, attr)
        updated = (1 - self._smoothing) * current + self._smoothing * target
        setattr(self._persona, attr, updated)

    def persona(self) -> Persona:
        """Return the current persona."""
        return self._persona

    def reset(self) -> None:
        """Reset to the neutral default persona."""
        self._persona = Persona()


def persona_block(persona: Persona) -> str:
    """
    Build a short system-prompt block describing the persona.

    Args:
        persona: The current persona.

    Returns:
        A formatted string for the system prompt.
    """
    lines: List[str] = ["Adapt your style to the user:"]
    if persona.formality > 0.65:
        lines.append("- Use formal, polite language.")
    elif persona.formality < 0.35:
        lines.append("- Use casual, friendly language.")
    else:
        lines.append("- Use a neutral register.")

    if persona.verbosity > 0.65:
        lines.append("- Be detailed and thorough.")
    elif persona.verbosity < 0.35:
        lines.append("- Be concise; prefer short answers.")
    else:
        lines.append("- Balance brevity and detail.")

    if persona.tone == "technical":
        lines.append("- Use precise technical vocabulary.")
    elif persona.tone == "friendly":
        lines.append("- Be warm and approachable.")

    return "\n".join(lines)
