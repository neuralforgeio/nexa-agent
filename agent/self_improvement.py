"""
Nexa Agent — Self-Improvement Reflection Loop
=============================================

This module lets Nexa *reflect* on its own past turns and extract
actionable improvements. Unlike the memory curator (which stores facts
about the user/world), the self-improvement loop stores **meta-rules**
about how to behave better next time.

The loop runs after each completed conversation turn:

    1. :func:`reflect_on_turn` compares the user's last message, the
       assistant's answer, the tool calls made, and any errors.
    2. It extracts one of three improvement types:
          - ``BEHAVIORAL_RULE``  — "next time X happens, do Y".
          - ``TOOL_PREFERENCE``  — "prefer tool A over tool B for task T".
          - ``AVOID``            — "don't do X again (caused error/waste)".
    3. The improvement is stored and surfaced in future system prompts
       via :func:`build_improvement_digest`.

The improvements are weighted by how often they're reinforced; stale or
contradicted rules decay over time.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Improvement type labels.
TYPE_BEHAVIORAL = "behavioral_rule"
TYPE_TOOL_PREF = "tool_preference"
TYPE_AVOID = "avoid"

# Signals that an answer was unsatisfactory (user rephrased / corrected).
REPHRASE_SIGNALS = (
    "no,", "not what", "wrong", "try again", "i meant", "actually,",
    "don't", "stop", "instead", "rather",
)

# Signals that a tool call was wasteful (slow + unneeded).
WASTE_SIGNALS = (
    "too slow", "took too long", "didn't need", "unnecessary",
)


@dataclass
class Improvement:
    """
    A single self-improvement rule.

    Attributes:
        kind:        One of ``TYPE_BEHAVIORAL`` / ``TYPE_TOOL_PREF`` / ``TYPE_AVOID``.
        trigger:    Short description of the triggering situation.
        action:     What to do (or not do) next time.
        weight:     Confidence/counter (≥ 1; grows when reinforced).
        created_at: Unix timestamp of creation.
        last_used:  Unix timestamp of last reinforcement (or ``None``).
        source:     Short provenance string (e.g. ``"turn#42"``).
    """

    kind: str
    trigger: str
    action: str
    weight: int = 1
    created_at: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    source: str = ""

    def reinforce(self) -> None:
        """Reinforce this improvement (+1 weight, refresh ``last_used``)."""
        self.weight += 1
        self.last_used = time.time()

    def decay(self, amount: int = 1) -> None:
        """Reduce the weight (used when a rule is contradicted)."""
        self.weight = max(0, self.weight - amount)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "kind": self.kind,
            "trigger": self.trigger,
            "action": self.action,
            "weight": self.weight,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "source": self.source,
        }


@dataclass
class TurnReflection:
    """
    The output of reflecting on a single turn.

    Attributes:
        improvements:  Improvements extracted from this turn (may be empty).
        signals:       Raw signals detected (for debugging/transparency).
        summary:       One-line human summary of the reflection.
    """

    improvements: List[Improvement] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    summary: str = ""


class SelfImprovementLoop:
    """
    Stateful self-improvement engine.

    Stores :class:`Improvement` items, deduplicates by trigger, and
    surfaces the highest-weighted ones in the system prompt.
    """

    def __init__(self, max_improvements: int = 50) -> None:
        """
        Initialize the loop.

        Args:
            max_improvements: Hard cap on stored improvements (LRU eviction).
        """
        self._improvements: List[Improvement] = []
        self._max = max_improvements
        self._trigger_index: Dict[str, Improvement] = {}

    # ---------------------------------------------------------------------
    # Reflection
    # ---------------------------------------------------------------------
    def reflect_on_turn(
        self,
        user_message: str,
        assistant_answer: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[str]] = None,
        turn_id: int = 0,
    ) -> TurnReflection:
        """
        Reflect on a completed turn and extract improvements.

        Args:
            user_message:     The user's last message.
            assistant_answer: The assistant's final answer.
            tool_calls:      List of ``{name, ok, duration_ms}`` dicts.
            errors:          List of error strings (if any).
            turn_id:         Monotonic turn number (for provenance).

        Returns:
            A :class:`TurnReflection` with extracted improvements.
        """
        signals: List[str] = []
        improvements: List[Improvement] = []
        source = f"turn#{turn_id}"

        msg_lower = user_message.lower()
        ans_lower = assistant_answer.lower()

        # Signal 1: user rephrased/corrected → behavioral rule.
        if any(s in msg_lower for s in REPHRASE_SIGNALS):
            signals.append("user_correction")
            improvements.append(
                Improvement(
                    kind=TYPE_BEHAVIORAL,
                    trigger="user rephrased or corrected the previous answer",
                    action="ask a clarifying question before committing to a long answer",
                    source=source,
                )
            )

        # Signal 2: an error occurred → avoid the failure path.
        if errors:
            signals.append(f"errors:{len(errors)}")
            first_err = errors[0][:200]
            improvements.append(
                Improvement(
                    kind=TYPE_AVOID,
                    trigger=f"error occurred: {first_err}",
                    action="detect this error category and apply the healer's plan before responding",
                    source=source,
                )
            )

        # Signal 3: wasteful tool calls → tool preference.
        if tool_calls:
            slow_calls = [c for c in tool_calls if (c.get("duration_ms", 0) or 0) > 5000]
            failed_calls = [c for c in tool_calls if not c.get("ok", True)]
            if slow_calls:
                signals.append(f"slow_tools:{[c.get('name') for c in slow_calls]}")
                improvements.append(
                    Improvement(
                        kind=TYPE_TOOL_PREF,
                        trigger=f"tool {slow_calls[0].get('name')} was slow (>5s)",
                        action="consider a faster alternative or skip if not strictly needed",
                        source=source,
                    )
                )
            if failed_calls:
                signals.append(f"failed_tools:{[c.get('name') for c in failed_calls]}")
                improvements.append(
                    Improvement(
                        kind=TYPE_AVOID,
                        trigger=f"tool {failed_calls[0].get('name')} failed",
                        action="validate inputs against the tool's schema before calling",
                        source=source,
                    )
                )

        # Signal 4: very terse user message + long answer → expand first.
        if len(user_message.split()) <= 4 and len(assistant_answer.split()) > 80:
            signals.append("terse_question_long_answer")
            improvements.append(
                Improvement(
                    kind=TYPE_BEHAVIORAL,
                    trigger="user asked a very short question",
                    action="run the prompt expander to ground the answer in context before responding",
                    source=source,
                )
            )

        # Signal 5: user complained about waste.
        if any(s in msg_lower for s in WASTE_SIGNALS):
            signals.append("user_waste_complaint")
            improvements.append(
                Improvement(
                    kind=TYPE_AVOID,
                    trigger="user signaled the response was wasteful (too slow/unnecessary)",
                    action="be more economical: fewer tool calls, shorter answers when possible",
                    source=source,
                )
            )

        # Register the improvements (dedup + reinforce existing).
        for imp in improvements:
            self._register(imp)

        summary = (
            f"Reflected on turn {turn_id}: "
            f"{len(improvements)} improvement(s), signals={signals}"
        )
        return TurnReflection(
            improvements=improvements, signals=signals, summary=summary
        )

    # ---------------------------------------------------------------------
    # Storage
    # ---------------------------------------------------------------------
    def _register(self, imp: Improvement) -> None:
        """Add ``imp`` or reinforce an existing one with the same trigger."""
        existing = self._trigger_index.get(imp.trigger)
        if existing:
            existing.reinforce()
            return
        self._improvements.append(imp)
        self._trigger_index[imp.trigger] = imp
        # Evict the lowest-weight item if over capacity.
        if len(self._improvements) > self._max:
            self._improvements.sort(key=lambda x: x.weight, reverse=True)
            evicted = self._improvements.pop()
            self._trigger_index.pop(evicted.trigger, None)

    # ---------------------------------------------------------------------
    # Digest
    # ---------------------------------------------------------------------
    def build_improvement_digest(self, max_items: int = 8) -> str:
        """
        Build a short system-prompt block from the highest-weighted rules.

        Args:
            max_items: Max number of rules to include.

        Returns:
            A formatted string, or ``""`` if no improvements exist.
        """
        if not self._improvements:
            return ""
        ranked = sorted(self._improvements, key=lambda x: x.weight, reverse=True)
        top = ranked[:max_items]
        lines: List[str] = ["Self-improvement rules learned from past turns:"]
        for imp in top:
            verb = {
                TYPE_BEHAVIORAL: "WHEN",
                TYPE_TOOL_PREF: "PREFER",
                TYPE_AVOID: "AVOID",
            }.get(imp.kind, "WHEN")
            lines.append(
                f"- ({imp.weight}x) {verb} {imp.trigger} → {imp.action}"
            )
        return "\n".join(lines)

    # ---------------------------------------------------------------------
    # Access + stats
    # ---------------------------------------------------------------------
    def all_improvements(self) -> List[Improvement]:
        """Return all stored improvements (highest weight first)."""
        return sorted(self._improvements, key=lambda x: x.weight, reverse=True)

    def stats(self) -> Dict[str, Any]:
        """Return a serializable summary."""
        by_kind: Dict[str, int] = {}
        for imp in self._improvements:
            by_kind[imp.kind] = by_kind.get(imp.kind, 0) + 1
        return {
            "total": len(self._improvements),
            "by_kind": by_kind,
            "top_trigger": (
                self._improvements[0].trigger if self._improvements else None
            ),
        }


# ---------------------------------------------------------------------------
# Convenience: reflect on a turn (stateless helper)
# ---------------------------------------------------------------------------
def reflect_on_turn(
    user_message: str,
    assistant_answer: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    errors: Optional[List[str]] = None,
    turn_id: int = 0,
) -> TurnReflection:
    """
    Stateless reflection helper (does not persist improvements).

    Use this when you only want the signals/summary without storing.
    For stateful reflection, use :class:`SelfImprovementLoop`.
    """
    loop = SelfImprovementLoop()
    return loop.reflect_on_turn(
        user_message, assistant_answer, tool_calls, errors, turn_id
    )
