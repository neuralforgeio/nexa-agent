"""
Nexa Agent — Context Compressor
==============================

Manages the conversation context window to prevent token-overflow errors.
Inspired by Hermes Agent's ``context_compressor`` and
``conversation_compression`` modules — original implementation.

Strategy:
    1. Estimate token count for the entire transcript.
    2. If over budget, identify the oldest removable messages (keeping
       the system prompt and most recent context).
    3. Summarize the old messages into a single compact "context summary"
       message using the LLM itself.
    4. Replace the old messages with the summary, preserving recency.

This enables long conversations without hitting context limits — the
agent "remembers" the gist of early messages via compression.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from typing import Any, Dict, List, Optional, Tuple

from agent.message_sanitizer import estimate_tokens

#: Default token budget for the context window.
DEFAULT_TOKEN_BUDGET = 30_000

#: Minimum messages to keep uncompressed (system + recent context).
MIN_KEEP_RECENT = 6

#: How many messages to compress in a single summarization pass.
COMPRESS_BATCH_SIZE = 10


class ContextCompressor:
    """
    Manages context window compression for long conversations.

    The compressor is stateless between calls — it operates on whatever
    transcript it's given. The :meth:`compress_if_needed` method is the
    main entry point.

    Attributes:
        token_budget:  The maximum tokens allowed in the context window.
        provider:      Optional LLM provider for summarization. If None,
                       compression falls back to truncation.
    """

    def __init__(
        self,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        provider: Optional[Any] = None,
    ) -> None:
        """
        Initialize the compressor.

        Args:
            token_budget: Max tokens before compression triggers.
            provider:     An LLM provider with a ``chat_completion`` method
                          for summarization. If None, falls back to
                          truncation-based compression.
        """
        self.token_budget = token_budget
        self.provider = provider

    def estimate_total_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Estimate the total token count of a message transcript.

        Includes role tags and separator tokens (approximate).

        Args:
            messages: The transcript.

        Returns:
            Estimated total token count.
        """
        total = 0
        for msg in messages:
            # ~4 tokens overhead per message for role + delimiters.
            total += 4
            content = msg.get("content", "")
            if isinstance(content, str):
                total += estimate_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += estimate_tokens(part["text"])
        return total

    def needs_compression(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Check if the transcript exceeds the token budget.

        Args:
            messages: The transcript.

        Returns:
            True if compression is needed.
        """
        return self.estimate_total_tokens(messages) > self.token_budget

    async def compress_if_needed(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Compress the transcript if it exceeds the token budget.

        Args:
            messages: The full transcript (system + history + user).

        Returns:
            A tuple of (compressed_messages, was_compressed).
        """
        if not self.needs_compression(messages):
            return messages, False

        # Identify the system prompt (first message if role=system).
        system_msgs = []
        rest = messages
        if messages and messages[0].get("role") == "system":
            system_msgs = [messages[0]]
            rest = messages[1:]

        # Keep the most recent messages, compress the older ones.
        keep_count = min(MIN_KEEP_RECENT, len(rest))
        to_compress = rest[:-keep_count] if keep_count > 0 else rest
        to_keep = rest[-keep_count:] if keep_count > 0 else []

        if not to_compress:
            return messages, False

        # Compress the old messages.
        if self.provider:
            summary = await self._summarize(to_compress)
        else:
            summary = self._truncate_compress(to_compress)

        compressed = (
            system_msgs
            + [
                {
                    "role": "system",
                    "content": f"[Context Summary]\n{summary}",
                }
            ]
            + to_keep
        )
        return compressed, True

    async def _summarize(self, messages: List[Dict[str, Any]]) -> str:
        """
        Use the LLM to summarize a batch of old messages.

        Args:
            messages: The messages to summarize.

        Returns:
            A compact summary string.
        """
        # Build a text representation of the messages.
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")
        transcript_text = "\n".join(lines)

        # Truncate the input if it's extremely long.
        if len(transcript_text) > 8000:
            transcript_text = transcript_text[:8000] + "\n…[truncated]"

        prompt = (
            "Summarize the following conversation segment concisely. "
            "Capture key facts, decisions, and any important context the "
            "agent should remember. Keep it under 500 words.\n\n"
            f"{transcript_text}\n\nSummary:"
        )

        try:
            response = await self.provider.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a conversation summarizer. Be concise.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            return response.get("content", "").strip() or self._truncate_compress(messages)
        except Exception:
            # Fallback to truncation if LLM summarization fails.
            return self._truncate_compress(messages)

    def _truncate_compress(self, messages: List[Dict[str, Any]]) -> str:
        """
        Fallback compression: extract first sentence of each message.

        Used when no LLM provider is available for summarization.

        Args:
            messages: The messages to compress.

        Returns:
            A truncated summary string.
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Take the first ~200 chars of each message.
            snippet = content[:200].replace("\n", " ")
            if len(content) > 200:
                snippet += "…"
            lines.append(f"[{role}] {snippet}")
        return "Earlier conversation (truncated):\n" + "\n".join(lines)
