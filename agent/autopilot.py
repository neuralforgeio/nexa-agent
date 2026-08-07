"""S-01: AutoPilot — goal → plan → execute → verify → iterate.

Drives a bounded autonomous loop over a single goal. Hard safety limits are
baked in (max iterations, wall-clock) so a runaway loop can never spin
forever. Every transition is recorded so callers can audit what happened.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional


@dataclass
class AutoPilotResult:
    goal: str
    status: str = "running"            # running | completed | failed | aborted
    iterations: int = 0
    trace: List[str] = field(default_factory=list)
    output: str = ""


class SafetyLimits:
    """Hard ceilings for any autonomous run (CLA Omega-class safeguards)."""

    MAX_ITERATIONS = 25
    MAX_SECONDS = 1800  # 30 min


class AutoPilot:
    def __init__(
        self,
        plan: Callable[[str], Awaitable[List[str]]],
        execute: Callable[[str], Awaitable[bool]],
        verify: Callable[[str], Awaitable[bool]],
        limits: SafetyLimits = SafetyLimits(),
    ) -> None:
        self.plan = plan
        self.execute = execute
        self.verify = verify
        self.limits = limits

    async def run(self, goal: str) -> AutoPilotResult:
        res = AutoPilotResult(goal=goal)
        start = time.monotonic()
        try:
            steps = await self.plan(goal)
            res.trace.append(f"plan: {len(steps)} steps")
            for i, step in enumerate(steps, 1):
                if i > self.limits.MAX_ITERATIONS:
                    res.status = "aborted"
                    res.trace.append(f"aborted: iteration cap {self.limits.MAX_ITERATIONS}")
                    return res
                if time.monotonic() - start > self.limits.MAX_SECONDS:
                    res.status = "aborted"
                    res.trace.append("aborted: wall-clock budget exceeded")
                    return res
                ok = await self.execute(step)
                res.iterations = i
                res.trace.append(f"step {i}: {'ok' if ok else 'exc-fail'}")
                if not ok:
                    res.status = "failed"
                    res.output = f"step {i} failed"
                    return res
            if await self.verify(goal):
                res.status = "completed"
                res.output = "goal achieved"
            else:
                res.status = "failed"
                res.output = "verification failed"
        except Exception as exc:  # pragma: no cover
            res.status = "failed"
            res.trace.append(f"exception: {exc}")
        return res
