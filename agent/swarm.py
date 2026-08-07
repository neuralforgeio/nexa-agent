"""S-02: Multi-agent parallel swarm.

Executes independent sub-agents in parallel over a shared asyncio event loop.
Failure of one agent does not cancel the others; results are combined
deterministically in input order.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Sequence


@dataclass
class AgentSpec:
    name: str
    task: str


@dataclass
class SwarmResult:
    results: List[Any] = field(default_factory=list)
    errors:  List[str] = field(default_factory=list)


async def swarm(agents: Sequence[AgentSpec], run_task: Callable[[str], Awaitable[Any]]) -> SwarmResult:
    """
    Run all ``agents`` concurrently with ``run_task`` and gather outcomes.

    Fail-soft: individual errors are collected, not raised, so one broken
    sub-agent cannot collapse the whole swarm.
    """
    res = SwarmResult()
    async def _run(spec: AgentSpec):
        try:
            res.results.append(await run_task(spec.task))
        except Exception as exc:
            res.errors.append(f"{spec.name}: {exc}")
    await asyncio.gather(*[_run(a) for a in agents])
    return res
