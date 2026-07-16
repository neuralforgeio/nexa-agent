"""
Tests for the error classifier module.

Verifies that API errors are correctly categorized into TRANSIENT, AUTH,
BAD_REQUEST, or FATAL, and that retry guidance is accurate.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest

from agent.error_classifier import (
    ErrorCategory,
    classify_error,
    is_context_overflow,
)


class TestErrorClassification:
    """Tests for the classify_error function."""

    def test_rate_limit_is_transient(self) -> None:
        """429 errors must be classified as TRANSIENT with retry=True."""
        err = Exception("Error code: 429 - Too many requests")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.TRANSIENT
        assert ce.should_retry is True
        assert ce.delay_ms > 0

    def test_server_error_is_transient(self) -> None:
        """5xx server errors must be classified as TRANSIENT."""
        err = Exception("Error code: 503 - Service unavailable")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.TRANSIENT
        assert ce.should_retry is True

    def test_timeout_is_transient(self) -> None:
        """Network timeouts must be classified as TRANSIENT."""
        err = Exception("Request timed out after 30s")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.TRANSIENT
        assert ce.should_retry is True

    def test_auth_error_no_retry(self) -> None:
        """401 errors must be classified as AUTH with retry=False."""
        err = Exception("Error code: 401 - Invalid API key")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.AUTH
        assert ce.should_retry is False

    def test_forbidden_no_retry(self) -> None:
        """403 errors must be classified as AUTH with retry=False."""
        err = Exception("Error code: 403 - Forbidden")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.AUTH
        assert ce.should_retry is False

    def test_context_overflow_is_bad_request(self) -> None:
        """Context length errors must be classified as BAD_REQUEST."""
        err = Exception("Error code: 400 - This model's maximum context length is 128000 tokens")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.BAD_REQUEST
        assert ce.should_retry is False

    def test_unknown_error_is_fatal(self) -> None:
        """Unclassifiable errors must be FATAL with retry=False."""
        err = Exception("Something completely unexpected happened")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.FATAL
        assert ce.should_retry is False

    def test_retry_after_hint_extracted(self) -> None:
        """The classifier should extract retry-after hints from error messages."""
        err = Exception("429 - Rate limited. Retry after 5 seconds")
        ce = classify_error(err)
        assert ce.category == ErrorCategory.TRANSIENT
        assert ce.delay_ms == 5000


class TestContextOverflow:
    """Tests for the is_context_overflow helper."""

    def test_context_overflow_detected(self) -> None:
        """is_context_overflow must return True for context-length errors."""
        err = Exception("maximum context length exceeded")
        assert is_context_overflow(err) is True

    def test_non_context_error_not_flagged(self) -> None:
        """is_context_overflow must return False for non-context errors."""
        err = Exception("Invalid API key")
        assert is_context_overflow(err) is False
