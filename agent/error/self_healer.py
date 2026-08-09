"""
OpenForge — Self-Healer (Improvement v2)
========================================

The Self-Healer takes a runtime error (traceback, exception, or failed
tool result) and produces a structured **healing plan**: a diagnosis of
the likely root cause and a concrete remediation recipe.

Unlike a generic "retry" loop, the healer *classifies* the error and
emits a typed remediation so the conversation loop can act on it:

    - ``NETWORK``      → switch provider / retry with backoff.
    - ``AUTH``         → prompt user for credentials.
    - ``CONTEXT_OVERFLOW`` → compress context and retry.
    - ``TOOL_ARG``     → re-call the tool with corrected arguments.
    - ``IMPORT``       → patch the import path.
    - ``ATTRIBUTE``    → fall back to an alternative implementation.
    - ``UNKNOWN``      → escalate to the user with a structured report.

The healer is **stateful**: it remembers the last N errors per session so
it can detect repeating failures and escalate instead of looping.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Error categories (healer-specific)
# ---------------------------------------------------------------------------
CAT_NETWORK = "network"
CAT_AUTH = "auth"
CAT_CONTEXT_OVERFLOW = "context_overflow"
CAT_TOOL_ARG = "tool_arg"
CAT_IMPORT = "import"
CAT_ATTRIBUTE = "attribute"
CAT_SYNTAX = "syntax"
CAT_TIMEOUT = "timeout"
CAT_UNKNOWN = "unknown"

# Pattern → category mapping (checked in order; first match wins).
HEAL_PATTERNS: List[tuple] = [
    (re.compile(r"connection|refused|timeout|timed out|unreachable|dns|resolve", re.I), CAT_NETWORK),
    (re.compile(r"\b401\b|\b403\b|unauthor|forbidden|invalid api key|api[_ ]?key", re.I), CAT_AUTH),
    (re.compile(r"context length|maximum context|too many tokens|context window", re.I), CAT_CONTEXT_OVERFLOW),
    (re.compile(r"json.*decode|missing.*argument|unexpected.*argument|invalid.*arg", re.I), CAT_TOOL_ARG),
    (re.compile(r"^importerror|^moduleNotFoundError|no module named", re.I | re.M), CAT_IMPORT),
    (re.compile(r"attributeError|has no attribute|object has no", re.I), CAT_ATTRIBUTE),
    (re.compile(r"syntaxError|unexpected (eof|indent|token)|unmatched", re.I), CAT_SYNTAX),
    (re.compile(r"\b429\b|rate limit|too many requests", re.I), CAT_TIMEOUT),
]


@dataclass
class HealingPlan:
    """
    A structured remediation plan for a runtime error.

    Attributes:
        category:       One of the ``CAT_*`` constants.
        root_cause:     Short human-readable diagnosis.
        remediation:    Concrete action to take.
        retry:          Whether a retry is safe.
        escalate:       Whether to escalate to the user.
        max_retries:    Suggested retry cap for this category.
        patch_hint:     Optional code patch hint (e.g. corrected import).
    """

    category: str
    root_cause: str
    remediation: str
    retry: bool = False
    escalate: bool = False
    max_retries: int = 2
    patch_hint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "category": self.category,
            "root_cause": self.root_cause,
            "remediation": self.remediation,
            "retry": self.retry,
            "escalate": self.escalate,
            "max_retries": self.max_retries,
            "patch_hint": self.patch_hint,
        }


# ---------------------------------------------------------------------------
# Healer
# ---------------------------------------------------------------------------
@dataclass
class _ErrorRecord:
    """Internal record of a past error for repetition detection."""
    category: str
    signature: str
    at: float = field(default_factory=time.monotonic)


class SelfHealer:
    """
    Stateful self-healing engine.

    Maintains a short history of recent errors so it can detect when the
    same error keeps recurring (and escalate instead of retrying forever).
    """

    def __init__(self, history_size: int = 10) -> None:
        """
        Initialize the healer.

        Args:
            history_size: Max number of recent errors to remember.
        """
        self._history: List[_ErrorRecord] = []
        self._history_size = history_size
        self.heal_count: int = 0
        self.escalation_count: int = 0

    # ---------------------------------------------------------------------
    # Classification
    # ---------------------------------------------------------------------
    def classify(self, error: Any) -> str:
        """
        Classify an error (exception or string) into a healer category.

        Args:
            error: An exception instance, a traceback string, or any object
                   with a ``str()`` representation.

        Returns:
            One of the ``CAT_*`` constants.
        """
        text = self._extract_text(error)
        for pattern, category in HEAL_PATTERNS:
            if pattern.search(text):
                return category
        return CAT_UNKNOWN

    @staticmethod
    def _extract_text(error: Any) -> str:
        """Pull a searchable text representation from ``error``."""
        if isinstance(error, BaseException):
            parts = [type(error).__name__, str(error)]
            cause = error.__cause__
            if cause:
                parts.append(str(cause))
            return "\n".join(parts)
        return str(error)

    # ---------------------------------------------------------------------
    # Plan generation
    # ---------------------------------------------------------------------
    def plan(self, error: Any, context: Optional[Dict[str, Any]] = None) -> HealingPlan:
        """
        Produce a :class:`HealingPlan` for ``error``.

        Args:
            error:   The error to heal.
            context: Optional dict with extra info (``tool_name``,
                     ``file_path``, ``provider_name``, …).

        Returns:
            A :class:`HealingPlan` describing how to remediate.
        """
        category = self.classify(error)
        text = self._extract_text(error)
        ctx = context or {}
        repeating = self._is_repeating(category, text)

        plans: Dict[str, HealingPlan] = {
            CAT_NETWORK: HealingPlan(
                category=CAT_NETWORK,
                root_cause="Network/connection failure reaching the provider.",
                remediation="Failover to the next provider in the chain, then retry.",
                retry=True,
                max_retries=3,
            ),
            CAT_AUTH: HealingPlan(
                category=CAT_AUTH,
                root_cause="Authentication failed (invalid or missing API key).",
                remediation="Switch to a provider with valid credentials or prompt the user.",
                retry=False,
                escalate=True,
                max_retries=0,
            ),
            CAT_CONTEXT_OVERFLOW: HealingPlan(
                category=CAT_CONTEXT_OVERFLOW,
                root_cause="The conversation exceeded the model's context window.",
                remediation="Compress older messages, then retry with the shorter transcript.",
                retry=True,
                max_retries=1,
            ),
            CAT_TOOL_ARG: HealingPlan(
                category=CAT_TOOL_ARG,
                root_cause="A tool was called with malformed or missing arguments.",
                remediation="Parse the tool's expected schema, re-call with corrected arguments.",
                retry=True,
                max_retries=2,
                patch_hint=self._suggest_tool_arg_patch(text, ctx),
            ),
            CAT_IMPORT: HealingPlan(
                category=CAT_IMPORT,
                root_cause="A module or name could not be imported.",
                remediation="Patch the import path; ensure the package is installed.",
                retry=True,
                max_retries=1,
                patch_hint=self._suggest_import_patch(text),
            ),
            CAT_ATTRIBUTE: HealingPlan(
                category=CAT_ATTRIBUTE,
                root_cause="An attribute access failed on an unexpected object.",
                remediation="Fall back to an alternative implementation or guard with hasattr.",
                retry=True,
                max_retries=1,
            ),
            CAT_SYNTAX: HealingPlan(
                category=CAT_SYNTAX,
                root_cause="Generated code had a syntax error.",
                remediation="Re-prompt the LLM to regenerate the code with strict syntax.",
                retry=True,
                max_retries=1,
            ),
            CAT_TIMEOUT: HealingPlan(
                category=CAT_TIMEOUT,
                root_cause="The provider rate-limited or timed out the request.",
                remediation="Back off exponentially, then retry; failover if it persists.",
                retry=True,
                max_retries=3,
            ),
            CAT_UNKNOWN: HealingPlan(
                category=CAT_UNKNOWN,
                root_cause="Unclassified error; no automatic remediation known.",
                remediation="Escalate to the user with a structured error report.",
                retry=False,
                escalate=True,
                max_retries=0,
            ),
        }

        plan = plans[category]
        # If this exact error is repeating, escalate even if normally retryable.
        if repeating:
            plan.escalate = True
            plan.retry = False
            plan.remediation = (
                f"Same error ({category}) is repeating. Escalating to avoid a loop. "
                + plan.remediation
            )
            self.escalation_count += 1

        # Record this error in history.
        self._history.append(
            _ErrorRecord(category=category, signature=self._signature(text))
        )
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

        self.heal_count += 1
        return plan

    # ---------------------------------------------------------------------
    # Patch hints
    # ---------------------------------------------------------------------
    @staticmethod
    def _suggest_import_patch(text: str) -> str:
        """Extract a likely module name from an ImportError message."""
        m = re.search(r"No module named ['\"]?([\w.]+)", text, re.I)
        if m:
            return f"Check that '{m.group(1)}' is installed and on sys.path."
        return ""

    @staticmethod
    def _suggest_tool_arg_patch(text: str, ctx: Dict[str, Any]) -> str:
        """Suggest a fix for a malformed tool-call argument."""
        tool = ctx.get("tool_name", "the tool")
        if "json" in text.lower():
            return f"Re-encode the arguments for {tool} as valid JSON before calling."
        if "missing" in text.lower():
            return f"Inspect {tool}'s schema and supply the missing required argument."
        return f"Validate arguments against {tool}'s schema before retrying."

    # ---------------------------------------------------------------------
    # Repetition detection
    # ---------------------------------------------------------------------
    @staticmethod
    def _signature(text: str) -> str:
        """Produce a coarse signature for repetition detection."""
        # Normalize whitespace + lowercase, drop numbers (line numbers change).
        norm = re.sub(r"\d+", "N", text).strip().lower()
        return norm[:200]

    def _is_repeating(self, category: str, text: str) -> bool:
        """Return ``True`` if the same error signature was seen recently."""
        sig = self._signature(text)
        for rec in self._history[-5:]:
            if rec.category == category and rec.signature == sig:
                return True
        return False

    # ---------------------------------------------------------------------
    # Reporting
    # ---------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """Return a serializable summary of the healer's activity."""
        return {
            "heal_count": self.heal_count,
            "escalation_count": self.escalation_count,
            "recent_errors": [
                {"category": r.category, "at": r.at} for r in self._history[-5:]
            ],
        }
