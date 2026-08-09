"""
OpenForge — Proactive Suggester
================================

Suggests the next action the user might want, based on the conversation
state. These suggestions are surfaced in the UI (e.g. as suggestion
chips) or injected into the assistant's closing line.

The suggester is rule-based + stateful — it tracks what the user has
done so far and proposes the next logical step.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Suggestion templates.
SUGGEST_RUN_TESTS = "Run the test suite to verify the change."
SUGGEST_COMMIT = "Commit the change with a descriptive message."
SUGGEST_SEARCH = "Search the web for more context."
SUGGEST_EXPLAIN = "Explain what this code does."
SUGGEST_REFORMAT = "Reformat the code to match the project style."
SUGGEST_DOCS = "Add a docstring to the new function."
SUGGEST_REFACTOR = "Refactor this to reduce duplication."
SUGGEST_DEPLOY = "Verify the change deploys correctly."
SUGGEST_REVIEW = "Review the diff before pushing."
SUGGEST_NEW_TASK = "What would you like to work on next?"


@dataclass
class Suggestion:
    """
    A single suggested next action.

    Attributes:
        text:     The suggestion text.
        kind:     Category label (e.g. ``"test"``, ``"commit"``).
        priority: 0 (highest) … N. Lower is more relevant.
    """

    text: str
    kind: str = "general"
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {"text": self.text, "kind": self.kind, "priority": self.priority}


class ProactiveSuggester:
    """
    Stateful proactive suggester.

    Call :meth:`observe` after each turn with what happened, then
    :meth:`suggest` to get the next suggestions.
    """

    def __init__(self) -> None:
        self._last_actions: List[str] = []
        self._code_was_written: bool = False
        self._tests_were_run: bool = False
        self._was_committed: bool = False
        self._errors_seen: int = 0

    def observe(
        self,
        action: str,
        tools_used: Optional[List[str]] = None,
        had_error: bool = False,
    ) -> None:
        """
        Record what happened in the last turn.

        Args:
            action:      Short label (e.g. ``"wrote_code"``, ``"ran_tests"``).
            tools_used:  Tools invoked.
            had_error:   Whether an error occurred.
        """
        self._last_actions.append(action)
        if len(self._last_actions) > 20:
            self._last_actions = self._last_actions[-20:]
        if action == "wrote_code":
            self._code_was_written = True
        elif action == "ran_tests":
            self._tests_were_run = True
        elif action == "committed":
            self._was_committed = True
        if had_error:
            self._errors_seen += 1

    def suggest(self, max_items: int = 4) -> List[Suggestion]:
        """
        Return up to ``max_items`` proactive suggestions.

        Suggestions are ordered by priority (most relevant first).
        """
        out: List[Suggestion] = []

        # If we just wrote code and haven't tested → suggest tests.
        if self._code_was_written and not self._tests_were_run:
            out.append(Suggestion(SUGGEST_RUN_TESTS, "test", 0))

        # If tests passed and not committed → suggest commit.
        if self._tests_were_run and not self._was_committed and self._errors_seen == 0:
            out.append(Suggestion(SUGGEST_COMMIT, "commit", 1))

        # If we wrote code, suggest adding docs.
        if self._code_was_written:
            out.append(Suggestion(SUGGEST_DOCS, "docs", 2))

        # If the last action was a search, suggest going deeper.
        if self._last_actions and self._last_actions[-1] == "searched":
            out.append(Suggestion(SUGGEST_EXPLAIN, "explain", 2))

        # If errors were seen, suggest reviewing.
        if self._errors_seen > 0:
            out.append(Suggestion(SUGGEST_REVIEW, "review", 1))

        # Always offer the open-ended "what next?" if we have room.
        if len(out) < max_items:
            out.append(Suggestion(SUGGEST_NEW_TASK, "general", 5))

        return out[:max_items]

    def reset(self) -> None:
        """Clear state."""
        self._last_actions.clear()
        self._code_was_written = False
        self._tests_were_run = False
        self._was_committed = False
        self._errors_seen = 0


def suggestion_block(suggestions: List[Suggestion]) -> str:
    """
    Build a short block for the assistant's closing line.

    Args:
        suggestions: The suggestions to format.

    Returns:
        A formatted string, or ``""`` if no suggestions.
    """
    if not suggestions:
        return ""
    lines: List[str] = ["Suggested next steps:"]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s.text}")
    return "\n".join(lines)
