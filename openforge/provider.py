"""
OpenForge — LLM Provider
=========================

This module wraps :class:`openai.AsyncOpenAI` with:

- Retry with exponential backoff for transient errors (429 / 5xx).
- Native streaming via ``stream=True`` yielding token deltas.
- Automatic tool-call dispatch through the :class:`~tools.registry.ToolRegistry`.

The :meth:`LLMProvider.chat_stream` method is the core entry point used by
:class:`~agent.OpenForgeAgent`. It yields ``("token", text)`` tuples for content
deltas and ``("tool_call", result)`` tuples for executed tools.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from .config import NEXA_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL, NEXA_NAME, NEXA_VERSION
from tools.registry import ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Provider capability detection
# ---------------------------------------------------------------------------
def _env_flag(name: str, default: str = "") -> str:
    """Read an env flag as lowercase string (empty if unset)."""
    return os.environ.get(name, default).strip().lower()


def _supports_tools(base_url: Optional[str]) -> bool:
    """
    Return whether the endpoint at ``base_url`` advertises tool calling.

    Resolution order:
      1. ``NEXA_LLM_SUPPORTS_TOOLS=0/false/no`` — force OFF (escape hatch).
      2. ``NEXA_LLM_SUPPORTS_TOOLS=1/true/yes`` — force ON.
      3. Heuristic on the URL host: providers known to lack function-calling
         (llama.cpp with embedding-only models, ollama tool-less models) are
         OFF unless explicitly forced on.

    Args:
        base_url: The provider's OpenAI-compatible base URL.

    Returns:
        ``True`` if tools may be sent to this provider.
    """
    flag = _env_flag("NEXA_LLM_SUPPORTS_TOOLS")
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    url = (base_url or "").lower()
    # llama.cpp servers that only advertise `completion` capability often
    # choke on `tools` payloads. Default ON for llamacpp (modern builds DO
    # support tool calling); users can force off via env if their build
    # doesn't.
    return True


# Characters a model might emit that look like a tool call but are just text.
_TOOL_LIKE_PREFIXES = ("<tool_call", "{\"", "```json", "Action:")


def _is_tools_unsupported(err_text: str) -> bool:
    """
    Return whether an error indicates the endpoint rejected the tools payload.

    llama.cpp builds without ``--jinja`` return HTTP 400 with messages like
    ``"tools are not supported"`` or ``"tools param requires --jinja"``.
    LM Studio returns similar 4xx errors when tools are passed to a model
    that can't consume them.

    Args:
        err_text: The stringified exception from the OpenAI client.

    Returns:
        ``True`` if the payload should be retried without ``tools``.
    """
    t = err_text.lower()
    markers = (
        "tools param",
        "tools are not supported",
        "tool_choice",
        "requires --jinja",
        "does not support tool",
        "unsupported parameter: tools",
        "unknown field `tools`",
        "unrecognized request argument: tools",
    )
    return any(m in t for m in markers)


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
            model:    Override for ``FORGE_MODEL``. Defaults to config.
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base_url or (OPENAI_BASE_URL or None)
        self.model = model or NEXA_MODEL
        self._client: Optional[AsyncOpenAI] = None

    @classmethod
    def from_active_provider(cls) -> "LLMProvider":
        """
        Build an LLMProvider from the active registry provider.

        This makes TokenRouter/others the first-class runtime path: when the
        user has activated a provider via ``nexa provider use <name>`` or the
        Web UI, the agent will talk to that endpoint rather than the env
        defaults.
        """
        try:
            from openforge.provider_registry import ProviderRegistry
            cfg = ProviderRegistry().get_active()
            if cfg is not None:
                return cls(api_key=cfg.api_key, base_url=cfg.base_url, model=cfg.model)
        except Exception:
            pass
        return cls()  # env/config defaults (slowest good path)

    async def _get_client(self) -> AsyncOpenAI:
        """
        Lazily create and cache the ``AsyncOpenAI`` client.

        Returns:
            The singleton ``AsyncOpenAI`` instance.
        """
        if self._client is None:
            kwargs: Dict[str, Any] = {
                "api_key": self.api_key,
                # Long timeout — local providers (llamacpp) can be slow.
                "timeout": float(os.environ.get("FORGE_LLM_TIMEOUT", "600")),
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        registry: Optional[ToolRegistry] = None,
        *,
        _depth: int = 0,
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
        in a follow-up call, then continues streaming.

        Capability negotiation (v4.0):
            - If the provider does not support function calling (env-gated
              via ``NEXA_LLM_SUPPORTS_TOOLS`` or a 4xx "tools not supported"
              response), the tools payload is dropped and the completion
              proceeds as plain text. This prevents llama.cpp builds without
              tool support from hanging/cancelling the request.

        Args:
            messages: The conversation transcript (list of role/content dicts).
            tools:    OpenAI-format tool schemas (from ``registry.get_openai_schemas()``).
            registry: The tool registry used to dispatch tool calls.
            _depth:   Internal recursion guard for the tool follow-up call.

        Yields:
            Tuples of ``(event_type, payload)`` as described above.
        """
        client = await self._get_client()

        # v4.0: capability negotiation — drop tools if unsupported.
        send_tools = bool(tools) and registry is not None and _supports_tools(self.base_url)

        # Attempt 1: streaming call.
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
            }
            if send_tools:
                kwargs["tools"] = tools

            stream = await client.chat.completions.create(**kwargs)

            accumulated_content = ""
            accumulated_tool_calls: List[Any] = []

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Yield reasoning deltas first (models running with
                # --reasoning-preserve emit <think>…</think> here).
                reasoning_delta = getattr(delta, "reasoning_content", None)
                if reasoning_delta:
                    yield ("reasoning", reasoning_delta)

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
            # `_depth` caps recursion so a misbehaving model can't loop forever.
            if accumulated_tool_calls and registry and _depth < 8:
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
                    # Attach the original arguments so the UI can display
                    # exactly what the model requested.
                    result.args = tc["arguments"]
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
                    messages, tools, registry, _depth=_depth + 1
                ):
                    yield (event_type, payload)
                return

            yield ("done", None)

        except Exception as exc:
            errtext = str(exc)
            # v4.0: if the server rejects the tools payload (llama.cpp without
            # tool support returns 400), retry once WITHOUT tools.
            if send_tools and _depth == 0 and _is_tools_unsupported(errtext):
                async for event_type, payload in self.chat_stream(
                    messages, None, None, _depth=_depth + 8
                ):
                    yield (event_type, payload)
                return

            if _is_transient(exc):
                # Retry with exponential backoff (max 3 retries).
                for attempt in range(3):
                    await asyncio.sleep(2 ** attempt)
                    try:
                        async for event_type, payload in self.chat_stream(
                            messages, tools if send_tools else None, registry, _depth=_depth
                        ):
                            yield (event_type, payload)
                        return
                    except Exception as retry_exc:
                        if attempt == 2:
                            yield ("error", str(retry_exc))
                        continue
            else:
                yield ("error", errtext)

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
