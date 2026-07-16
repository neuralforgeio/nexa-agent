"""
Nexa Agent — Error Classifier
=============================

Classifies LLM API errors into categories so the agent can apply the
appropriate retry strategy. Inspired by Hermes Agent's ``error_classifier``
module — original implementation.

Error categories:
    TRANSIENT   — 429 rate limit, 5xx server error, network timeout.
                  → Retry with exponential backoff + jitter.
    AUTH        — 401/403 invalid key, expired token.
                  → Do not retry; surface to user.
    BAD_REQUEST — 400 malformed request, context too long.
                  → Do not retry; may trigger context compression.
    FATAL       — Unknown/unrecoverable errors.
                  → Do not retry; log and surface.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    """The category of an LLM API error."""

    TRANSIENT = "transient"
    """Retryable: rate limits, server errors, timeouts."""

    AUTH = "auth"
    """Authentication failure: bad key, expired token. Do not retry."""

    BAD_REQUEST = "bad_request"
    """Malformed request or context too long. Do not retry blindly."""

    FATAL = "fatal"
    """Unrecoverable. Do not retry."""


@dataclass
class ClassifiedError:
    """
    The result of classifying an error.

    Attributes:
        category:     The :class:`ErrorCategory`.
        should_retry: Whether a retry is worthwhile.
        delay_ms:     Suggested backoff delay in milliseconds (0 if no retry).
        reason:       Human-readable explanation.
    """

    category: ErrorCategory
    should_retry: bool
    delay_ms: int
    reason: str


# Pattern → (category, reason) mappings. Checked in order; first match wins.
_ERROR_PATTERNS: list[tuple[re.Pattern, ErrorCategory, str]] = [
    (re.compile(r"429|rate.?limit|too many requests", re.I), ErrorCategory.TRANSIENT,
     "Rate limited by provider"),
    (re.compile(r"503|service unavailable|overloaded", re.I), ErrorCategory.TRANSIENT,
     "Provider server overloaded"),
    (re.compile(r"502|bad gateway", re.I), ErrorCategory.TRANSIENT,
     "Bad gateway from provider"),
    (re.compile(r"500|internal server error", re.I), ErrorCategory.TRANSIENT,
     "Provider internal error"),
    (re.compile(r"timeout|timed out|ETIMEDOUT|ECONNRESET|ECONNREFUSED|fetch failed", re.I),
     ErrorCategory.TRANSIENT, "Network timeout or connection reset"),
    (re.compile(r"401|unauthorized|invalid api key|token expired|incorrect", re.I),
     ErrorCategory.AUTH, "Invalid or expired API key"),
    (re.compile(r"403|forbidden|permission denied", re.I), ErrorCategory.AUTH,
     "Access forbidden by provider"),
    (re.compile(r"context.?length|maximum context|token limit|too long", re.I),
     ErrorCategory.BAD_REQUEST, "Context length exceeded"),
    (re.compile(r"400|bad request|invalid request", re.I), ErrorCategory.BAD_REQUEST,
     "Malformed request"),
]


def classify_error(err: Exception) -> ClassifiedError:
    """
    Classify an LLM API error into a category with retry guidance.

    Args:
        err: The exception raised by the OpenAI SDK or a tool.

    Returns:
        A :class:`ClassifiedError` with the category, retry flag, and
        suggested backoff delay.

    Example::

        try:
            await provider.chat_completion(...)
        except Exception as e:
            ce = classify_error(e)
            if ce.should_retry:
                await asyncio.sleep(ce.delay_ms / 1000)
                # retry...
            else:
                raise
    """
    text = str(err)

    for pattern, category, reason in _ERROR_PATTERNS:
        if pattern.search(text):
            if category == ErrorCategory.TRANSIENT:
                return ClassifiedError(
                    category=category,
                    should_retry=True,
                    delay_ms=_backoff_delay(text),
                    reason=reason,
                )
            return ClassifiedError(
                category=category,
                should_retry=False,
                delay_ms=0,
                reason=reason,
            )

    # Unknown error — treat as fatal, do not retry.
    return ClassifiedError(
        category=ErrorCategory.FATAL,
        should_retry=False,
        delay_ms=0,
        reason=f"Unclassified error: {text[:200]}",
    )


def _backoff_delay(text: str) -> int:
    """
    Calculate an exponential backoff delay with jitter.

    For rate-limit errors, we start at 1s and increase. A small random
    jitter (0–500ms) is added to avoid thundering-herd retries.

    Args:
        text: The error message text (used to detect retry-after hints).

    Returns:
        Delay in milliseconds.
    """
    import random

    # Try to extract a "retry after N seconds" hint.
    match = re.search(r"retry.?after[:\s]*(\d+)", text, re.I)
    if match:
        return int(match.group(1)) * 1000

    # Default: 1s base + jitter.
    base_ms = 1000
    jitter = random.randint(0, 500)
    return base_ms + jitter


def is_context_overflow(err: Exception) -> bool:
    """
    Check if an error indicates the context window was exceeded.

    This is used to trigger context compression before retrying.

    Args:
        err: The exception to check.

    Returns:
        True if the error is a context-overflow error.
    """
    ce = classify_error(err)
    return ce.category == ErrorCategory.BAD_REQUEST and "context" in ce.reason.lower()
