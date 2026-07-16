"""
Nexa Agent — LLM Provider
=========================

This module wraps :class:`openai.AsyncOpenAI` with:

- Retry with exponential backoff for transient errors (429 / 5xx).
- Native streaming via ``stream=True`` yielding token deltas.
- Automatic tool-call dispatch through the :class:`~tools.registry.ToolRegistry`.

The :meth:`LLMProvider.chat_stream` method is the core entry point used by
:class:`~agent.NexaAgent`. It yields ``("token", text)`` tuples for content
deltas and ``("tool_call", result)`` tuples for executed tools.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from .config import NEXA_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL, NEXA_NAME, NEXA_VERSION
from tools.registry import ToolRegistry, ToolResult


def _is_transient(err: Exception) -> bool:
    """
    Check whether an error is likely transient (retryable).

    Args:
        err: The exception to inspect.

    Returns:
        ``True`` if the error message mentions rate limits, timeouts, or
        5xx server errors.
    """
    text = str(err).lower()
    keywords = ["429", "rate limit", "too many requests", "timeout", "503", "502", "500", "connection"]
    return any(k in text for k in keywords)


class LLMProvider:
    """
    Thin abstraction over :class:`openai.AsyncOpenAI`.

    The provider owns the SDK client and exposes :meth:`chat_stream` for
    streaming completions with tool-calling support.

    Attributes:
        model:  The model identifier (e.g. ``"gpt-4o"``).
        client: The underlying ``AsyncOpenAI`` instance (lazy-initialized).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize the provider.

        Args:
            api_key:  Override for ``OPENAI_API_KEY``. Defaults to config.
            base_url: Override for ``OPENAI_BASE_URL``. Defaults to config.
            model:    Override for ``NEXA_MODEL``. Defaults to config.
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base_url or (OPENAI_BASE_URL or None)
        self.model = model or NEXA_MODEL
        self._client: Optional[AsyncOpenAI] = None

    async def _get_client(self) -> AsyncOpenAI:
        """
        Lazily create and cache the ``AsyncOpenAI`` client.

        Returns:
            The singleton ``AsyncOpenAI`` instance.
        """
        if self._client is None:
            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        registry: Optional[ToolRegistry] = None,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Stream a chat completion with tool-calling support.

        This method yields tuples of ``(event_type, payload)``:

        - ``("token", str)`` — a content delta from the model.
        - ``("tool_call", ToolResult)`` — the result of an executed tool.
        - ``("done", None)`` — the stream completed normally.
        - ``("error", str)`` — an error occurred.

        If the model requests tool calls, this method executes them via
        the provided ``registry`` and feeds the results back to the model
        in a follow-up (non-streaming) call, then continues streaming.

        Args:
            messages: The conversation transcript (list of role/content dicts).
            tools:    OpenAI-format tool schemas (from ``registry.get_openai_schemas()``).
            registry: The tool registry used to dispatch tool calls.

        Yields:
            Tuples of ``(event_type, payload)`` as described above.
        """
        client = await self._get_client()

        # Attempt 1: streaming call.
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            stream = await client.chat.completions.create(**kwargs)

            accumulated_content = ""
            accumulated_tool_calls: List[Any] = []

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Yield content deltas.
                if delta.content:
                    accumulated_content += delta.content
                    yield ("token", delta.content)

                # Accumulate tool call fragments.
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        while len(accumulated_tool_calls) <= tc.index:
                            accumulated_tool_calls.append(
                                {"id": "", "name": "", "arguments": ""}
                            )
                        slot = accumulated_tool_calls[tc.index]
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["arguments"] += tc.function.arguments

            # If the model requested tools, execute and feed back.
            if accumulated_tool_calls and registry:
                # Build the assistant message with tool_calls.
                messages.append(
                    {
                        "role": "assistant",
                        "content": accumulated_content or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in accumulated_tool_calls
                        ],
                    }
                )

                # Execute each tool call.
                for tc in accumulated_tool_calls:
                    name = tc["name"]
                    try:
                        args = json.loads(tc["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result: ToolResult = await registry.execute(name, **args)
                    yield ("tool_call", result)
                    # Append the tool result to the transcript.
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result.output,
                        }
                    )

                # Follow-up call to get the final answer.
                async for event_type, payload in self.chat_stream(
                    messages, tools, registry
                ):
                    yield (event_type, payload)
                return

            yield ("done", None)

        except Exception as exc:
            if _is_transient(exc):
                # Retry with exponential backoff (max 3 retries).
                for attempt in range(3):
                    await asyncio.sleep(2 ** attempt)
                    try:
                        async for event_type, payload in self.chat_stream(
                            messages, tools, registry
                        ):
                            yield (event_type, payload)
                        return
                    except Exception as retry_exc:
                        if attempt == 2:
                            yield ("error", str(retry_exc))
                        continue
            else:
                yield ("error", str(exc))

    @staticmethod
    def build_system_prompt(body: str) -> str:
        """
        Build the system prompt with Nexa Agent identity.

        Args:
            body: The body of the system prompt (tool catalog, memory, etc.).

        Returns:
            The full system prompt string.
        """
        return (
            f"You are {NEXA_NAME} v{NEXA_VERSION}, an advanced AI agent.\n"
            "You reason step by step and may use tools to ground your answers.\n"
            "Be concise, accurate and helpful. When you need to use a tool, "
            "call it via the function-calling interface and stop; the runtime "
            "will execute it and feed the result back to you.\n\n"
            f"{body}"
        )
