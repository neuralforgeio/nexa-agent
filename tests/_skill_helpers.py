"""
Shared helpers for skill tests.

`ScriptedProvider` is a deterministic stand-in *only* for the LLM boundary:
it speaks the `chat_stream(messages) -> async (event, payload)` contract, so
real file reads, schema validation, and prompt construction all run for real.
Live llama.cpp coverage lives behind the `NEXA_E2E_LLAMACPP=1` gate.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple


class ScriptedProvider:
    """Scripted async provider compatible with skills._llm.chat."""

    def __init__(
        self,
        reply: str = "{}",
        events: Optional[List[Tuple[str, Any]]] = None,
        fail: bool = False,
    ) -> None:
        self.reply = reply
        self.events = events
        self.fail = fail
        self.calls: List[List[Dict[str, Any]]] = []

    async def chat_stream(self, messages, tools=None, registry=None, **kw) -> AsyncGenerator:
        self.calls.append(list(messages))
        if self.fail:
            yield ("error", "scripted llm failure")
            return
        if self.events is not None:
            for ev in self.events:
                yield ev
        else:
            for i in range(0, len(self.reply), 7):
                yield ("token", self.reply[i : i + 7])
        yield ("done", None)

    # Convenience for assertions
    def last_user_message(self, messages: List[Dict[str, Any]]) -> str:
        return (messages[-1] or {}).get("content", "")
