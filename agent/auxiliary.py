"""S-05/S-06/S-07: auxiliary autonomous tools (harvester, ToT planner, scheduler)."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, List, Optional, Tuple

# ── S-05: background knowledge harvester ──────────────────────────────────────

class KnowledgeHarvester:
    """After ``idle_seconds`` without activity, search for requested topics and
    cache the findings into the knowledge base (background, non-blocking)."""

    def __init__(self, search: Callable[[str], Awaitable[Any]], cache: Any) -> None:
        self.search = search
        self.cache = cache
        self._task: Optional[asyncio.Task] = None

    async def start(self, topics: List[str], idle_seconds: float = 300.0) -> None:
        async def _loop() -> None:
            await asyncio.sleep(idle_seconds)
            for t in topics:
                try:
                    res = await self.search(t)
                    if hasattr(self.cache, "put"):
                        self.cache.put(t, res)
                except Exception:
                    continue
        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None


# ── S-06: Tree-of-Thoughts planner ────────────────────────────────────────────

class ToTPlanner:
    """Generate N candidate plans, score each, and return the best."""

    def __init__(self, generator: Callable[[str], Awaitable[List[str]]], scorer: Callable[[str], float]) -> None:
        self.generator = generator
        self.scorer = scorer

    async def best_plan(self, goal: str, breadth: int = 3) -> Tuple[List[str], float]:
        candidates = await self.generator(goal)  # list of plan-texts
        scored = sorted(((self.scorer(p), p) for p in candidates), reverse=True)
        best_score, best = scored[0] if scored else (0.0, "")
        return best.splitlines(), best_score


# ── S-07: Cron / scheduled tasks ──────────────────────────────────────────────

class Scheduler:
    """Minimal in-process cron: run a callable on a fixed interval."""

    def __init__(self) -> None:
        self._jobs: List[Tuple[asyncio.Task, Callable[[], Awaitable[Any]], float]] = []

    def every(self, seconds: float, job: Callable[[], Awaitable[Any]]) -> None:
        async def _loop() -> None:
            while True:
                await asyncio.sleep(seconds)
                try:
                    await job()
                except Exception:
                    continue
        self._jobs.append((asyncio.create_task(_loop()), job, seconds))

    async def stop_all(self) -> None:
        for task, _job, _s in self._jobs:
            task.cancel()
        self._jobs.clear()
