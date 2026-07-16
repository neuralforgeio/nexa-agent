"""
Nexa Agent — Learning Graph
===========================

Tracks patterns of successful and unsuccessful outcomes, enabling the
agent to make better decisions over time. Original implementation.
``learning_graph`` and ``learning_mutations`` modules — original
implementation.

The learning graph stores nodes (tools, approaches, patterns) with
success/failure counts. The agent can query this graph to:
    - Prefer tools with high success rates.
    - Avoid approaches that consistently fail.
    - Surface learning statistics in the /doctor command.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from typing import Any, Dict, List, Optional

from nexa.state import ConversationDB


class LearningGraph:
    """
    Tracks tool and pattern outcomes for data-driven decision-making.

    Attributes:
        db: The :class:`~storage.ConversationDB` for persistence.
    """

    def __init__(self, db: ConversationDB) -> None:
        """Initialize the learning graph with a database handle."""
        self.db = db

    async def record_tool_outcome(self, tool_name: str, success: bool) -> None:
        """
        Record the outcome of a tool execution.

        Args:
            tool_name: The name of the tool that was executed.
            success:   True if the tool succeeded, False otherwise.
        """
        await self.db.record_outcome("tool", tool_name, success)

    async def record_pattern_outcome(
        self, pattern: str, success: bool
    ) -> None:
        """
        Record the outcome of a problem-solving pattern.

        A "pattern" is a higher-level approach (e.g. "read-then-edit",
        "search-then-summarize") rather than a specific tool.

        Args:
            pattern: The pattern identifier.
            success: True if the approach worked.
        """
        await self.db.record_outcome("pattern", pattern, success)

    async def get_tool_success_rate(self, tool_name: str) -> Optional[float]:
        """
        Get the historical success rate for a tool.

        Args:
            tool_name: The tool to query.

        Returns:
            Success rate (0.0–1.0), or None if no data.
        """
        return await self.db.get_success_rate("tool", tool_name)

    async def recommend_tools(self, available: List[str]) -> List[str]:
        """
        Rank available tools by historical success rate.

        Tools with no data are placed in the middle (neutral). Tools with
        high failure rates sink to the bottom.

        Args:
            available: List of available tool names.

        Returns:
            The tools sorted by recommendation (best first).
        """
        scored: List[tuple[str, float]] = []
        for tool in available:
            rate = await self.get_tool_success_rate(tool)
            # No data → 0.5 (neutral). Higher is better.
            score = rate if rate is not None else 0.5
            scored.append((tool, score))

        # Sort by score descending.
        scored.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in scored]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregate learning statistics.

        Returns:
            A dict with conversation/message/memory counts and per-tool
            success/failure breakdowns.
        """
        return await self.db.get_learning_stats()
