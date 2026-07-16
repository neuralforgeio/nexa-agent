"""
Nexa Agent — Agent Runner
=========================

This module defines :class:`NexaAgent`, the main agent class that ties
together the LLM provider, tool registry, and storage layer. It also
provides a ``main()`` entry point for running the agent standalone.

Usage as a library::

    from run_agent import NexaAgent
    agent = NexaAgent(provider_name="ollama", model="llama3.2")
    async for event in agent.run_streaming("Hello", conv_id="..."):
        print(event)

Usage as a CLI::

    python run_agent.py --provider ollama --model llama3.2 "Hello, Nexa!"

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import argparse
import asyncio
import sys
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.conversation_loop import run_conversation
from agent.prompt_builder import build_system_prompt
from nexa_constants import NEXA_MAX_CONTEXT_MESSAGES, NEXA_NAME
from provider import LLMProvider
from providers.catalog import resolve_provider
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
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        registry: Optional[ToolRegistry] = None,
        db: Optional[ConversationDB] = None,
    ) -> None:
        """
        Initialize the agent.

        Args:
            provider_name: Provider name from the catalog (e.g. ``"ollama"``).
            model:         Override the model identifier.
            api_key:       Override the API key.
            base_url:      Override the base URL.
            registry:      Override the default tool registry.
            db:            Override the default storage instance.
        """
        # Resolve provider config.
        resolved_url, resolved_model, resolved_key = resolve_provider(provider_name)
        self.provider = LLMProvider(
            api_key=api_key or resolved_key,
            base_url=base_url or resolved_url,
            model=model or resolved_model,
        )
        self.registry = registry or create_default_registry()
        self.db = db or ConversationDB()

    def _build_transcript(
        self, user_input: str, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build the message transcript from system prompt, history, and input.

        Args:
            user_input: The latest user message.
            history:    Prior messages (oldest first).

        Returns:
            The full transcript ready for the LLM API call.
        """
        system_prompt = build_system_prompt(self.registry)
        transcript: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in history[-NEXA_MAX_CONTEXT_MESSAGES:]:
            if msg.get("role") == "system":
                continue
            transcript.append({"role": msg["role"], "content": msg["content"]})
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

        Yields event dicts with a ``type`` key (see
        :func:`agent.conversation_loop.run_conversation`).

        Args:
            user_input: The user's message text.
            conv_id:    The conversation ID (for persistence).
            history:    Prior messages from storage (optional).

        Yields:
            Event dicts.
        """
        await self.db.init()
        await self.db.add_message(conv_id, "user", user_input)

        history = history or []
        transcript = self._build_transcript(user_input, history)

        accumulated: List[str] = []
        async for event in run_conversation(self.provider, self.registry, transcript):
            if event["type"] == "token":
                accumulated.append(event["text"])
            elif event["type"] == "tool_result":
                tr = event["result"]
                await self.db.add_message(conv_id, "tool", tr["output"], tr["tool"])
            yield event

        answer = "".join(accumulated) or "(no response)"
        await self.db.add_message(conv_id, "assistant", answer)


async def _run_single_turn(agent: NexaAgent, message: str) -> None:
    """
    Run a single non-interactive turn and print events to stdout.

    Args:
        agent:  The :class:`NexaAgent` instance.
        message: The user message.
    """
    conv = await agent.db.create_conversation(title=message[:48])
    async for event in agent.run_streaming(message, conv["id"]):
        if event["type"] == "token":
            print(event["text"], end="", flush=True)
        elif event["type"] == "tool_result":
            print(f"\n[tool: {event['name']}] {event['result']['output'][:200]}")
        elif event["type"] == "done":
            print(f"\n[{NEXA_NAME}] done.")
        elif event["type"] == "error":
            print(f"\n[error] {event['message']}", file=sys.stderr)


def main() -> None:
    """
    CLI entry point for ``python run_agent.py``.

    Examples::

        python run_agent.py --provider openai "Hello"
        python run_agent.py --provider ollama --model llama3.2 "Hello"
        python run_agent.py --provider llamacpp "Hello"
    """
    parser = argparse.ArgumentParser(
        description=f"{NEXA_NAME} — standalone agent runner",
    )
    parser.add_argument("message", nargs="?", help="The message to send")
    parser.add_argument("--provider", default=None, help="Provider name (ollama, openai, llamacpp, ...)")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument("--base-url", default=None, help="Custom base URL")
    parser.add_argument("--api-key", default=None, help="API key override")
    args = parser.parse_args()

    if not args.message:
        parser.print_help()
        sys.exit(1)

    agent = NexaAgent(
        provider_name=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )
    asyncio.run(_run_single_turn(agent, args.message))


if __name__ == "__main__":
    main()
