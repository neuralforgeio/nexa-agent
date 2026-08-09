"""
OpenForge — Gateway base class (v4.3.0)
=========================================

Shared lifecycle for chat-platform gateways (Telegram, Discord, Slack,
Matrix, Email, Webhook). Each gateway:

  1. Connects to its platform (polling or event-driven).
  2. Maps the platform user_id to an app-level forge session via the session
     mapper.
  3. Forwards text messages to the orchestrator (`agent.orchestrator`).
  4. Sends the assistant's reply back as a platform-specific message.

Sub-classes must implement :
    - ``start()`` — begin listening.
    - ``stop()`` — gracefully terminate.
    - ``health_check()`` — lightweight status probe.
    - ``send_message(session_id, text)`` — deliver to the platform.
    - ``format_reply(text)`` — escape for that platform (Markdown / HTML).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class GatewayConfig:
    """Settings a gateway needs to start."""

    enabled: bool = False
    auth_token: str = ""          # bearer token, or empty for polling gateways
    allowed_users: frozenset = field(default_factory=frozenset)
    rate_limit_per_minute: int = 30


class GatewayBase(ABC):
    """
    Abstract base for all chat-platform gateways.

    Attributes:
        config: The :class:`GatewayConfig` for this gateway.
        session_mapper: Platform user-id → forge session id mapping.
    """

    name: str = "gateway"  # subclass must override

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        self.config = config or GatewayConfig()
        self.session_mapper: Dict[str, str] = {}
        self._started_at: Optional[float] = None
        self._health = "unknown"

    # ----- Lifecycle ------------------------------------------------------
    @abstractmethod
    async def start(self) -> None:
        """Begin listening on the platform."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Graceful shutdown."""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return a dict with at least ``ok`` and ``detail`` keys."""
        ...

    # ----- Messaging -------------------------------------------------------
    @abstractmethod
    async def send_message(self, session_id: str, text: str) -> Dict[str, Any]:
        """Send an assistant reply back to a user."""
        ...

    @abstractmethod
    def format_reply(self, text: str) -> str:
        """Sanitize markdown (or plain text) so the platform renders it."""
        ...

    # ----- Session mapping -------------------------------------------------
    def session_for(self, platform_user_id: str) -> str:
        """Return the existing session ID for a platform user, creating one."""
        if platform_user_id not in self.session_mapper:
            self.session_mapper[platform_user_id] = f"{self.name}-{platform_user_id}"
        return self.session_mapper[platform_user_id]

    # ----- Rate limiting (optional; subclasses may override) ---------------
    async def is_user_allowed(self, platform_user_id: str) -> bool:
        """Whitelist guard. Default: allow everyone."""
        if not self.config.allowed_users:
            return True
        return platform_user_id in self.config.allowed_users

    # ----- Diagnostics ------------------------------------------------------
    def uptime_seconds(self) -> float:
        return (time.time() - self._started_at) if self._started_at else 0.0

    def mark_started(self) -> None:
        self._started_at = time.time()
        self._health = "ok"


# ---------------------------------------------------------------------------
# Convenience registry shared by all gateways
# ---------------------------------------------------------------------------

_ACTIVE_GATEWAYS: Dict[str, GatewayBase] = {}


def register_active_gateway(name: str, gateway: GatewayBase) -> None:
    _ACTIVE_GATEWAYS[name] = gateway


def unregister_active_gateway(name: str) -> None:
    _ACTIVE_GATEWAYS.pop(name, None)


def active_gateway_names() -> list[str]:
    return sorted(_ACTIVE_GATEWAYS.keys())
