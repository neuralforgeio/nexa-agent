"""
Nexa Agent — Core Agent Loop
============================

This module defines :class:`NexaAgent`, the orchestrator that ties together
the LLM provider, tool registry, and storage layer.

The agent runs an iterative loop:

1. Assemble the system prompt (identity + tool catalog + memory).
2. Build the transcript (system + history + user input).
3. Call the provider's streaming method.
4. If the model requests a tool, the provider executes it and feeds the
   result back — this repeats until the model produces a final answer.
5. Persist the user message, tool results, and final answer to storage.

The :meth:`run_streaming` method is an async generator that yields events
for real-time UI updates.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from config import (
    NEXA_MAX_CONTEXT_MESSAGES,
    NEXA_MAX_TOOL_ITERATIONS,
    NEXA_NAME,
    NEXA_TAGLINE,
)
from provider import LLMProvider
from storage import ConversationDB
from tools.registry import ToolRegistry, create_default_registry


class NexaAgent:
    """
    The core Nexa Agent — orchestrates LLM calls, tool execution, and storage.

    Attributes:
        provider: The :class:`~provider.LLMProvider` instance.
        registry: The :class:`~tools.registry.ToolRegistry` with all tools.
        db:       The :class:`~storage.ConversationDB` for persistence.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        registry: Optional[ToolRegistry] = None,
        db: Optional[ConversationDB] = None,
    ) -> None:
        """
        Initialize the agent with optional dependency injection.

        Args:
            provider: Override the default LLM provider.
            registry: Override the default tool registry.
            db:       Override the default storage instance.
        """
        self.provider = provider or LLMProvider()
        self.registry = registry or create_default_registry()
        self.db = db or ConversationDB()

    def _build_system_prompt(self) -> str:
        """
        Assemble the system prompt with identity, tool catalog, and tagline.

        Returns:
            The full system prompt string.
        """
        tool_catalog = self.registry.describe()
        body = (
            f"# Tools\n"
            f"You have access to the following tools. Call them via the "
            f"function-calling interface when needed.\n\n"
            f"{tool_catalog}\n\n"
            f"# About\n"
            f"{NEXA_NAME} — {NEXA_TAGLINE}\n"
        )
        return LLMProvider.build_system_prompt(body)

    def _build_transcript(
        self, user_input: str, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build the message transcript from system prompt, history, and input.

        Args:
            user_input: The latest user message.
            history:    Prior messages (oldest first). Trimmed to
                :data:`NEXA_MAX_CONTEXT_MESSAGES`.

        Returns:
            The full transcript ready for the LLM API call.
        """
        transcript: List[Dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        for msg in history[-NEXA_MAX_CONTEXT_MESSAGES:]:
            if msg.get("role") == "system":
                continue
            entry: Dict[str, Any] = {
                "role": msg["role"],
                "content": msg["content"],
            }
            if msg.get("tool_name"):
                entry["name"] = msg["tool_name"]
            transcript.append(entry)
        transcript.append({"role": "user", "content": user_input})
        return transcript

    async def run_streaming(
        self,
        user_input: str,
        conv_id: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run a streaming conversation turn.

        Yields events as dicts with a ``type`` key:

        - ``{"type": "thinking"}`` — the agent started processing.
        - ``{"type": "token", "text": "..."}`` — a content delta.
        - ``{"type": "tool_call", "name": "...", "result": {...}}`` — a tool executed.
        - ``{"type": "done", "answer": "..."}`` — the final answer.
        - ``{"type": "error", "message": "..."}`` — an error occurred.

        The user message, tool results, and final answer are persisted to
        the database during the run.

        Args:
            user_input: The user's message text.
            conv_id:    The conversation ID (for persistence).
            history:    Prior messages from storage (optional).

        Yields:
            Event dicts as described above.
        """
        # Persist the user message immediately.
        await self.db.add_message(conv_id, "user", user_input)

        # Build transcript.
        history = history or []
        transcript = self._build_transcript(user_input, history)
        tools = self.registry.get_openai_schemas()

        yield {"type": "thinking"}

        # Collect the final answer and tool results.
        accumulated_answer: List[str] = []
        tool_results: List[Dict[str, Any]] = []
        error_message: Optional[str] = None

        async for event_type, payload in self.provider.chat_stream(
            transcript, tools=tools, registry=self.registry
        ):
            if event_type == "token":
                accumulated_answer.append(payload)
                yield {"type": "token", "text": payload}
            elif event_type == "tool_call":
                result_dict = payload.to_dict()
                tool_results.append(result_dict)
                yield {
                    "type": "tool_call",
                    "name": result_dict["tool"],
                    "result": result_dict,
                }
            elif event_type == "done":
                pass  # handled after loop
            elif event_type == "error":
                error_message = payload

        if error_message:
            answer = f"[{NEXA_NAME}] {error_message}"
            yield {"type": "error", "message": error_message}
        else:
            answer = "".join(accumulated_answer) or "(no response)"

        # Persist tool results.
        for tr in tool_results:
            await self.db.add_message(conv_id, "tool", tr["output"], tr["tool"])
        # Persist the final answer.
        await self.db.add_message(conv_id, "assistant", answer)

        yield {"type": "done", "answer": answer}
