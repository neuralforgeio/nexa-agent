"""
Nexa Agent — LLM Provider
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

from .constants import NEXA_API_KEY, NEXA_BASE_URL, NEXA_DEFAULT_MODEL, NEXA_NAME, NEXA_VERSION


class LLMProvider:
    """Wraps AsyncOpenAI with retry/backoff and streaming support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or NEXA_API_KEY
        self.base_url = base_url or NEXA_BASE_URL or None
        self.model = model or NEXA_DEFAULT_MODEL
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        thinking: bool = False,
    ) -> Dict[str, Any]:
        """Run a single chat completion with retry/backoff."""
        client = await self._get_client()
        max_retries = 4
        last_error = None
        for attempt in range(max_retries):
            try:
                kwargs: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                }
                if tools:
                    kwargs["tools"] = tools
                completion = await client.chat.completions.create(**kwargs)
                choice = completion.choices[0]
                return {
                    "content": choice.message.content or "",
                    "tool_calls": choice.message.tool_calls,
                    "model": self.model,
                    "raw": completion,
                }
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1 and _is_transient(e):
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise last_error  # type: ignore

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream token deltas. Yields content strings."""
        client = await self._get_client()
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    @staticmethod
    def build_system_prompt(body: str) -> str:
        return (
            f"You are {NEXA_NAME} v{NEXA_VERSION}, an advanced AI agent.\n"
            "You reason step by step and may use tools to ground your answers.\n"
            "Be concise, accurate and helpful.\n\n"
            f"{body}"
        )


def _is_transient(err: Exception) -> bool:
    """Check if an error is transient (retryable)."""
    text = str(err).lower()
    keywords = ["429", "rate limit", "too many requests", "timeout", "503", "502", "500", "connection"]
    return any(k in text for k in keywords)
