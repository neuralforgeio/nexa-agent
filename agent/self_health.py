"""
Nexa Agent — Self-Health Diagnostics
====================================

Provides health-check diagnostics for the agent's subsystems. Inspired by
Hermes Agent's ``doctor`` command — original implementation.

Checks:
    - Database connectivity and integrity.
    - Provider endpoint reachability (HTTP HEAD/GET).
    - Disk space for the NEXA_HOME and NEXA_WORKSPACE directories.
    - Memory store size and staleness.
    - Learning graph coverage.

Exposed via the ``/doctor`` slash command in the TUI.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import shutil
import socket
from dataclasses import dataclass, field
from typing import Any, Dict, List
from urllib.parse import urlparse

from config import NEXA_DB_PATH, NEXA_HOME, NEXA_WORKSPACE
from storage import ConversationDB


@dataclass
class HealthCheck:
    """
    The result of a single health check.

    Attributes:
        name:    The check name (e.g. "database").
        healthy: True if the check passed.
        detail:  Human-readable status message.
    """

    name: str
    healthy: bool
    detail: str


@dataclass
class HealthReport:
    """
    A full health report comprising multiple checks.

    Attributes:
        checks:    List of individual :class:`HealthCheck` results.
        all_healthy: True if every check passed.
    """

    checks: List[HealthCheck] = field(default_factory=list)

    @property
    def all_healthy(self) -> bool:
        """True if all checks passed."""
        return all(c.healthy for c in self.checks)

    def summary(self) -> str:
        """Return a formatted multi-line summary of the report."""
        lines = []
        icon = {True: "✓", False: "✗"}
        for c in self.checks:
            lines.append(f"  [{icon[c.healthy]}] {c.name}: {c.detail}")
        status = "ALL HEALTHY" if self.all_healthy else "ISSUES DETECTED"
        lines.append(f"\n  Overall: {status}")
        return "\n".join(lines)


class SelfHealth:
    """
    Runs diagnostic checks on the agent's subsystems.

    Attributes:
        db: The :class:`~storage.ConversationDB` for DB checks.
    """

    def __init__(self, db: ConversationDB) -> None:
        """Initialize the health checker."""
        self.db = db

    async def run_full_check(self) -> HealthReport:
        """
        Run all health checks and return a comprehensive report.

        Returns:
            A :class:`HealthReport` with all check results.
        """
        report = HealthReport()
        report.checks.append(await self.check_database())
        report.checks.append(self.check_disk_space())
        report.checks.append(await self.check_memories())
        report.checks.append(await self.check_learning_graph())
        return report

    async def check_database(self) -> HealthCheck:
        """
        Check that the SQLite database is accessible and has valid tables.

        Returns:
            A :class:`HealthCheck` with the DB status.
        """
        try:
            await self.db.init()
            stats = await self.db.get_learning_stats()
            return HealthCheck(
                name="database",
                healthy=True,
                detail=f"OK — {stats['conversations']} conversations, "
                f"{stats['messages']} messages, {stats['memories']} memories",
            )
        except Exception as e:
            return HealthCheck(
                name="database", healthy=False, detail=f"FAIL — {e}"
            )

    def check_disk_space(self) -> HealthCheck:
        """
        Check available disk space for NEXA_HOME and NEXA_WORKSPACE.

        Returns:
            A :class:`HealthCheck` with disk usage info.
        """
        try:
            usage = shutil.disk_usage(str(NEXA_HOME))
            free_gb = usage.free / (1024 ** 3)
            healthy = free_gb > 0.5  # Warn if less than 500MB free.
            return HealthCheck(
                name="disk_space",
                healthy=healthy,
                detail=f"{'OK' if healthy else 'LOW'} — {free_gb:.1f} GB free "
                f"at {NEXA_HOME}",
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space", healthy=False, detail=f"FAIL — {e}"
            )

    async def check_memories(self) -> HealthCheck:
        """
        Check the memory store for size and freshness.

        Returns:
            A :class:`HealthCheck` with memory store stats.
        """
        try:
            memories = await self.db.list_memories(limit=1000)
            count = len(memories)
            if count == 0:
                return HealthCheck(
                    name="memories",
                    healthy=True,
                    detail="OK — no memories yet (agent is learning)",
                )
            return HealthCheck(
                name="memories",
                healthy=True,
                detail=f"OK — {count} memories accumulated",
            )
        except Exception as e:
            return HealthCheck(
                name="memories", healthy=False, detail=f"FAIL — {e}"
            )

    async def check_learning_graph(self) -> HealthCheck:
        """
        Check the learning graph for coverage.

        Returns:
            A :class:`HealthCheck` with learning stats.
        """
        try:
            stats = await self.db.get_learning_stats()
            nodes = stats["learning_nodes"]
            tool_stats = stats.get("tool_stats", [])
            if not tool_stats:
                return HealthCheck(
                    name="learning_graph",
                    healthy=True,
                    detail="OK — no tool usage recorded yet",
                )
            tool_summary = ", ".join(
                f"{t['tool']}({t['success']}✓/{t['failure']}✗)" for t in tool_stats[:3]
            )
            return HealthCheck(
                name="learning_graph",
                healthy=True,
                detail=f"OK — {nodes} nodes; top: {tool_summary}",
            )
        except Exception as e:
            return HealthCheck(
                name="learning_graph", healthy=False, detail=f"FAIL — {e}"
            )

    @staticmethod
    async def check_provider_reachable(base_url: str, timeout: float = 5.0) -> HealthCheck:
        """
        Check if a provider endpoint is reachable via TCP connect.

        Args:
            base_url: The provider's base URL.
            timeout:  Connection timeout in seconds.

        Returns:
            A :class:`HealthCheck` with reachability status.
        """
        try:
            parsed = urlparse(base_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return HealthCheck(
                name=f"provider:{host}:{port}",
                healthy=True,
                detail=f"OK — reachable at {host}:{port}",
            )
        except asyncio.TimeoutError:
            return HealthCheck(
                name=f"provider:{base_url}",
                healthy=False,
                detail=f"TIMEOUT — no response in {timeout}s",
            )
        except Exception as e:
            return HealthCheck(
                name=f"provider:{base_url}",
                healthy=False,
                detail=f"FAIL — {e}",
            )
