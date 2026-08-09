"""
OpenForge — Provider Failover Engine
=====================================

This module implements automatic failover across multiple LLM providers.
When the active provider fails (network error, 5xx, auth, etc.), the engine
selects the next healthy provider from a configurable chain and retries.

Key components:
    - :class:`ProviderHealth`        — per-provider health snapshot.
    - :class:`ProviderHealthTracker` — tracks failures, cooldowns, latency.
    - :class:`FailoverChain`         — ordered list of providers + selection.
    - :func:`check_provider_health`  — async TCP/HTTP probe via httpx.
    - :func:`build_default_chain`    — sensible default chain from catalog + env.

Design goals:
    - **Non-blocking**: never sleeps the event loop synchronously.
    - **Cross-platform**: pure Python + httpx (works on Windows/Linux/Mac).
    - **Opt-in**: if no chain is configured, the agent behaves as before.
    - **Observable**: every failover is recorded for transparency.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

from providers.catalog import PROVIDER_CATALOG, ProviderConfig, resolve_provider


# ---------------------------------------------------------------------------
# Tunable defaults
# ---------------------------------------------------------------------------
DEFAULT_COOLDOWN_SECONDS: float = 30.0
"""How long a provider stays unhealthy after a failure."""

DEFAULT_MAX_FAILURES: int = 3
"""Failures before a provider is marked unhealthy."""

DEFAULT_HEALTH_TIMEOUT: float = 5.0
"""Timeout (seconds) for the TCP/HTTP health probe."""

DEFAULT_HEALTH_PROBE_PATH: str = "/v1/models"
"""Endpoint probed for OpenAI-compatible health checks."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ProviderHealth:
    """
    Mutable health snapshot for a single provider.

    Attributes:
        name:           Provider identifier (e.g. ``"openai"``).
        base_url:       The OpenAI-compatible API base URL.
        model:          Default model for this provider.
        api_key:        API key (local providers accept dummy).
        failures:       Consecutive failure counter.
        last_success:   Monotonic timestamp of last success (or ``None``).
        last_failure:   Monotonic timestamp of last failure (or ``None``).
        cooldown_until: Monotonic timestamp until which the provider is
                        considered unhealthy (or ``None`` if healthy).
        avg_latency_ms: Rolling average latency in milliseconds (or ``None``).
        notes:          Free-form capability/cost annotation used by
                        cost-aware / capability-aware failover (I-08, I-09).
    """

    name: str
    base_url: str
    model: str
    api_key: str
    notes: str = ""  # e.g. "cheap", "vision"
    failures: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    cooldown_until: Optional[float] = None
    avg_latency_ms: Optional[float] = None

    @property
    def is_healthy(self) -> bool:
        """Return ``True`` if the provider is currently usable."""
        if self.cooldown_until is None:
            return True
        return time.monotonic() >= self.cooldown_until


@dataclass
class FailoverPolicy:
    """
    Policy parameters governing failover behavior.

    Attributes:
        cooldown_seconds: How long to disable a failed provider.
        max_failures:     Failures before the provider is disabled.
        probe_timeout:    Timeout for the optional health probe.
        probe_on_select:  If ``True``, probe a provider before selecting it.
    """

    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    max_failures: int = DEFAULT_MAX_FAILURES
    probe_timeout: float = DEFAULT_HEALTH_TIMEOUT
    probe_on_select: bool = False


# ---------------------------------------------------------------------------
# Health tracker
# ---------------------------------------------------------------------------
class ProviderHealthTracker:
    """
    Tracks the health of every provider in a failover chain.

    The tracker is the single source of truth for which providers are
    currently usable. It records successes, failures, and cooldowns.
    """

    def __init__(
        self,
        providers: List[ProviderHealth],
        policy: Optional[FailoverPolicy] = None,
    ) -> None:
        """
        Initialize the tracker.

        Args:
            providers: The ordered list of provider health records.
            policy:    Optional policy override. Defaults to :class:`FailoverPolicy`.
        """
        self._providers: Dict[str, ProviderHealth] = {p.name: p for p in providers}
        self.policy: FailoverPolicy = policy or FailoverPolicy()
        self.failover_log: List[Dict[str, Any]] = []

    def get(self, name: str) -> Optional[ProviderHealth]:
        """Return the health record for ``name`` (or ``None``)."""
        return self._providers.get(name)

    def all_providers(self) -> List[ProviderHealth]:
        """Return all provider records in chain order."""
        return list(self._providers.values())

    def healthy_providers(self) -> List[ProviderHealth]:
        """Return only the currently-healthy providers, in chain order."""
        return [p for p in self._providers.values() if p.is_healthy]

    def record_success(self, name: str, latency_ms: Optional[float] = None) -> None:
        """
        Record a successful call to ``name``.

        Resets the failure counter and clears any cooldown.

        Args:
            name:        The provider that succeeded.
            latency_ms:  Optional observed latency (rolling average updated).
        """
        p = self._providers.get(name)
        if p is None:
            return
        p.failures = 0
        p.last_success = time.monotonic()
        p.cooldown_until = None
        if latency_ms is not None:
            if p.avg_latency_ms is None:
                p.avg_latency_ms = float(latency_ms)
            else:
                # Exponential moving average (alpha = 0.3).
                p.avg_latency_ms = 0.7 * p.avg_latency_ms + 0.3 * float(latency_ms)

    def record_failure(self, name: str, reason: str = "") -> None:
        """
        Record a failed call to ``name``.

        Increments the failure counter; if it reaches ``max_failures``
        the provider is cooled down for ``cooldown_seconds``.

        Args:
            name:   The provider that failed.
            reason: Short human-readable failure reason (logged).
        """
        p = self._providers.get(name)
        if p is None:
            return
        p.failures += 1
        p.last_failure = time.monotonic()
        if p.failures >= self.policy.max_failures:
            p.cooldown_until = time.monotonic() + self.policy.cooldown_seconds
            self.failover_log.append(
                {
                    "from": name,
                    "reason": reason,
                    "failures": p.failures,
                    "cooldown_until": p.cooldown_until,
                    "timestamp": time.time(),
                }
            )

    def pick_next(
        self, exclude: Optional[set] = None, prefer: Optional[str] = None
    ) -> Optional[ProviderHealth]:
        """
        Pick the next healthy provider in chain order.

        Optional callers may bias selection by cost or capability:
        - prefer='cheap'   → call sites pick the cheapest healthy provider.
        - prefer='vision'  → call sites exclude providers that lack vision.
        This module does NOT hold pricing data itself — pricing lives in
        forge/cost_tracker.py; this method is a policy hook, not a fork.

        Returns:
            The next :class:`ProviderHealth`, or ``None`` if all are unhealthy.
        """
        exclude = exclude or set()
        candidates = [p for p in self.healthy_providers() if p.name not in exclude]
        if not candidates:
            return None
        if prefer == "cheap":
            try:
                from openforge.cost_tracker import _PRICING
            except Exception:
                _PRICING = {}
            return min(candidates, key=lambda p: _PRICING.get(p.name, 0.001))
        if prefer == "vision":
            vision_only = [p for p in candidates if "vision" in (p.notes or "").lower()]
            return vision_only[0] if vision_only else None
        return candidates[0]

    def stats(self) -> List[Dict[str, Any]]:
        """Return a serializable summary of every provider's health."""
        now = time.monotonic()
        out: List[Dict[str, Any]] = []
        for p in self._providers.values():
            out.append(
                {
                    "name": p.name,
                    "base_url": p.base_url,
                    "model": p.model,
                    "healthy": p.is_healthy,
                    "failures": p.failures,
                    "avg_latency_ms": p.avg_latency_ms,
                    "cooldown_remaining_s": (
                        max(0.0, p.cooldown_until - now)
                        if p.cooldown_until is not None
                        else 0.0
                    ),
                }
            )
        return out


# ---------------------------------------------------------------------------
# Failover chain
# ---------------------------------------------------------------------------
class FailoverChain:
    """
    Ordered list of providers with health-aware selection.

    The chain is consumed left-to-right. When the active provider fails
    repeatedly, :meth:`advance` moves the cursor to the next healthy one.
    """

    def __init__(
        self,
        providers: List[ProviderHealth],
        policy: Optional[FailoverPolicy] = None,
    ) -> None:
        if not providers:
            raise ValueError("FailoverChain requires at least one provider")
        self.tracker = ProviderHealthTracker(providers, policy)
        self._cursor: int = 0

    @property
    def active(self) -> ProviderHealth:
        """Return the currently-active provider (never ``None``)."""
        return list(self.tracker._providers.values())[self._cursor]

    def advance(self, reason: str = "") -> Optional[ProviderHealth]:
        """
        Mark the active provider as failed and advance to the next healthy one.

        Args:
            reason: Short failure reason for the log.

        Returns:
            The new active provider, or ``None`` if no healthy provider remains.
        """
        current = self.active
        self.tracker.record_failure(current.name, reason)
        nxt = self.tracker.pick_next(exclude={current.name})
        if nxt is None:
            return None
        # Move the cursor to the next healthy provider.
        names = list(self.tracker._providers.keys())
        self._cursor = names.index(nxt.name)
        self.tracker.failover_log.append(
            {
                "from": current.name,
                "to": nxt.name,
                "reason": reason,
                "timestamp": time.time(),
            }
        )
        return nxt

    def record_success(self, latency_ms: Optional[float] = None) -> None:
        """Record that the active provider succeeded."""
        self.tracker.record_success(self.active.name, latency_ms)

    def record_failure(self, reason: str = "") -> None:
        """Record that the active provider failed (without advancing)."""
        self.tracker.record_failure(self.active.name, reason)

    def all_healthy(self) -> bool:
        """Return ``True`` if at least one provider is healthy."""
        return bool(self.tracker.healthy_providers())

    def reset_cursor(self) -> None:
        """Move the cursor back to the first provider in the chain."""
        self._cursor = 0


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------
async def check_provider_health(
    base_url: str,
    api_key: str = "",
    timeout: float = DEFAULT_HEALTH_TIMEOUT,
    probe_path: str = DEFAULT_HEALTH_PROBE_PATH,
) -> Tuple[bool, Optional[float]]:
    """
    Probe an OpenAI-compatible endpoint for health.

    Sends a ``GET {base_url}{probe_path}`` request with the bearer token.
    A 200 response means healthy; anything else (or a network error) means
    unhealthy.

    Args:
        base_url:   The provider base URL (no trailing slash needed).
        api_key:    Bearer token (local providers accept any non-empty string).
        timeout:    Request timeout in seconds.
        probe_path: Path appended to ``base_url`` (default ``/v1/models``).

    Returns:
        A tuple ``(healthy, latency_ms)``. ``latency_ms`` is ``None`` on failure.
    """
    url = base_url.rstrip("/") + probe_path
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
        latency_ms = (time.monotonic() - start) * 1000.0
        return (resp.status_code == 200, latency_ms)
    except Exception:
        return (False, None)


# ---------------------------------------------------------------------------
# Default chain builder
# ---------------------------------------------------------------------------
def build_default_chain(
    primary_name: Optional[str] = None,
    failover_names: Optional[List[str]] = None,
    policy: Optional[FailoverPolicy] = None,
) -> FailoverChain:
    """
    Build a default failover chain from the catalog + environment.

    Resolution order for the primary provider:
        1. ``primary_name`` argument (if given).
        2. ``FORGE_PROVIDER`` env var.
        3. ``FORGE_BASE_URL`` env var (treated as ``"custom"``).
        4. ``"openai"`` fallback.

    Failover providers come from:
        1. ``failover_names`` argument (if given).
        2. ``FORGE_FAILOVER_CHAIN`` env var (comma-separated names).
        3. Empty (no failover — primary only).

    Local providers (ollama, llamacpp, lmstudio, vllm) are auto-appended
    as last-resort failover targets if they appear reachable; this keeps
    the chain useful without forcing remote calls.

    Args:
        primary_name:    Optional primary provider name.
        failover_names:  Optional list of failover provider names.
        policy:          Optional policy override.

    Returns:
        A ready-to-use :class:`FailoverChain`.
    """
    policy = policy or FailoverPolicy()

    # Resolve the primary provider.
    primary_base, primary_model, primary_key = resolve_provider(primary_name)
    primary_display = primary_name or os.environ.get("FORGE_PROVIDER", "openai")
    if primary_display not in PROVIDER_CATALOG and primary_display != "custom":
        primary_display = "openai"

    providers: List[ProviderHealth] = [
        ProviderHealth(
            name=primary_display,
            base_url=primary_base,
            model=primary_model,
            api_key=primary_key,
        )
    ]

    # Resolve failover providers.
    if failover_names is None:
        env_chain = os.environ.get("FORGE_FAILOVER_CHAIN", "")
        failover_names = (
            [n.strip().lower() for n in env_chain.split(",") if n.strip()]
            if env_chain
            else []
        )

    seen = {primary_display}
    for name in failover_names:
        if name in seen or name not in PROVIDER_CATALOG:
            continue
        cfg: ProviderConfig = PROVIDER_CATALOG[name]
        key = (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get(f"{name.upper()}_API_KEY")
            or ("dummy" if name in ("ollama", "llamacpp", "lmstudio", "vllm") else "")
        )
        providers.append(
            ProviderHealth(
                name=name,
                base_url=cfg.base_url,
                model=cfg.default_model,
                api_key=key,
            )
        )
        seen.add(name)

    return FailoverChain(providers, policy)


def is_failover_enabled() -> bool:
    """Return ``True`` if failover is enabled via env (default: off)."""
    return os.environ.get("FORGE_FAILOVER_ENABLED", "0").lower() in ("1", "true", "yes")
