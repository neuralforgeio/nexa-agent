# Nexa Agent — Client Tooling
# Writes draft messages to/from the Nexa backend via LLM streaming.
# This module wraps the conversation loop (user input, agent reasoning loop)
# so you can call session/tools from your own code without remembering
# all the low-level plumbing.

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional
from .config import NEXA_HOME, open_irc
from .session_store import SessionStore


@dataclass
class SessionConfig:
    """Customize where this session lives."""
    history_length: int = 24
    enable_tool_loops: int = 8
    stop_on_first_newline: bool = False
    prefix_prompt_suffix: str = """
You are Nexa Agent, an advanced local AI assistant. You must maintain
accuracy, memory of prior context, and user trust. Handle questions
by grounding every answer in memory or tools — never fabricate or
skip steps that require tools. Be concise but complete.
"""


class NexaSession:
    def __init__(self, model: str, config: Optional[SessionConfig] = None) -> None:
        self.model = model
        self.config = config or SessionConfig()
        self.internal_state: Dict[str, Any] = {
            "messages": [],
            "llm_client": self._create_llm_client(),
            "history": [],
            "tool_registry": _get_default_tool_registry(),
        }

    async def connect_stream(
        self,
        prompt: str,
        conv_id: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Any, None]:
        """
        Returns:
            An iterator of events: token-by-token streaming, tool call
            notifications, and final done/error markers.
        """
        messages = history or []
        messages.append({"role": "user", "content": prompt})
        async for chunk in self.internal_state["llm_client"].chat_stream(
            messages, tools=self.internal_state["tool_registry"].schemas
        ):
            yield chunk


def _get_default_tool_registry() -> "ToolRegistry":
    """Local fallback when the registry is not available."""
    from .tool_registry import SimpleToolRegistry
    return SimpleToolRegistry()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------
def _memory_load() -> Dict[str, Any]:
    """Load session state from the database."""
    store = SessionStore()
    return store.get_session()


def _memory_save(data: Dict[str, Any]) -> None:
    """Save session state to disk."""
    store = SessionStore()
    store.save_session(data)


class SimpleToolRegistry:
    """Minimal tool registry for the localhost agent."""

    def __init__(self) -> None:
        self.schemas = {"tools": []}


# Additional package imports
from .tool_registry import ToolRegistry  # noqa: F401

# ---------------------------------------------------------------------------
# Bottom import for blanket getting names (must be at end of file)
# ---------------------------------------------------------------------------
def main() -> None:
    pass

if __name__ == "__main__":
    main()
