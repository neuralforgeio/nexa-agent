"""
Nexa Agent — Iteration Budget
=============================

Tracks and enforces tool-call iteration limits per conversation turn.
Inspired by ``iteration_budget`` module — original
implementation.

The budget prevents infinite tool-calling loops where the model
repeatedly calls tools without producing a final answer. Each turn
gets a fresh budget that decrements on every LLM round-trip.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from dataclasses import dataclass, field
from typing import List

from openforge.constants import FORGE_MAX_TOOL_ITERATIONS


@dataclass
class IterationBudget:
    """
    Tracks the remaining iteration budget for a single conversation turn.

    Attributes:
        max_iterations: The maximum number of LLM round-trips allowed.
        used:           How many iterations have been consumed.
        history:        Record of each iteration's outcome.
    """

    max_iterations: int = FORGE_MAX_TOOL_ITERATIONS
    used: int = 0
    history: List[str] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        """How many iterations are left."""
        return max(0, self.max_iterations - self.used)

    @property
    def exhausted(self) -> bool:
        """True if no more iterations are allowed."""
        return self.used >= self.max_iterations

    def consume(self, outcome: str = "tool_call") -> bool:
        """
        Consume one iteration.

        Args:
            outcome: What happened this iteration ('tool_call', 'answer',
                     'error', 'retry').

        Returns:
            True if the iteration was consumed (budget remains), False if
            the budget is exhausted.
        """
        if self.exhausted:
            return False
        self.used += 1
        self.history.append(f"iter {self.used}: {outcome}")
        return True

    def summary(self) -> str:
        """Return a human-readable summary of the budget usage."""
        return (
            f"iterations: {self.used}/{self.max_iterations} used "
            f"({self.remaining} remaining)"
        )

    def reset(self) -> None:
        """Reset the budget for a new turn."""
        self.used = 0
        self.history.clear()
