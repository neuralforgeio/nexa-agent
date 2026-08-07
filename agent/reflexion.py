"""S-03: Reflexion loop — self-critique and auto-revise low-confidence outputs."""
from __future__ import annotations

from typing import Any, Optional


class ReflexionLoop:
    """Attach to an agent to self-review an answer when confidence is low."""

    def __init__(self, critique_fn) -> None:
        self.critique = critique_fn  # async def critique(output: str) -> bool (True = improved)

    async def maybe_revise(self, output: str, confidence: float) -> str:
        """
        Revise the output when confidence < 0.5. A critique_fn that returns
        True means the revision 'passed' the critic; False keeps the original.
        """
        if confidence >= 0.5:
            return output
        revised = await self.critique(output)
        return revised if revised else output
