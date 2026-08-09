"""
OpenForge — Provider Registry (v4.1.0)
========================================

Runtime provider management with secrets stored in
``~/.openforge/secrets/providers.json``. This module lets the user add, switch,
list, and remove LLM providers at runtime — without editing env vars or
restarting the agent.

Design goals:
    - **Single source of truth**: catalog defaults (openai, ollama, etc.)
      + user-defined custom providers (TokenRouter, Databricks, any
      OpenAI-compatible endpoint) live in one registry.
    - **Secret-safe**: api_keys are stored in ``~/.openforge/secrets/`` (which
      ``run_terminal_command`` cannot access — see ``tools.terminal_tool``).
    - **Masked display**: ``list_all()`` masks api_keys as ``tr_...wxyz``
      so logs / UIs never leak the full secret.
    - **Persistence**: active provider + custom configs survive restarts.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openforge.config import FORGE_SECRETS_DIR, ensure_nexa_home
from providers.catalog import PROVIDER_CATALOG, ProviderConfig, resolve_provider
from openforge.provider_failover import check_provider_health


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class StoredProviderConfig:
    """
    A provider config stored in ``providers.json``.

    Attributes:
        name:     Provider identifier (e.g. ``"tokenrouter"``).
        base_url: OpenAI-compatible API base URL.
        api_key:  API key (stored in secrets/, NOT displayed in list_all()).
        model:    Default model ID for this provider.
    """

    name: str
    base_url: str
    api_key: str = ""
    model: str = ""

    def __post_init__(self) -> None:
        """Ensure api_key is non-empty for local providers (llamacpp, ollama, lmstudio, vllm)."""
        local_providers = {"ollama", "llamacpp", "lmstudio", "vllm", "custom", "ornith"}
        if not self.api_key and (self.name in local_providers or "localhost" in self.base_url or "127.0.0.1" in self.base_url):
            self.api_key = "dummy"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StoredProviderConfig":
        """Build a StoredProviderConfig from a plain dict."""
        return cls(
            name=str(d.get("name", "")),
            base_url=str(d.get("base_url", "")),
            api_key=str(d.get("api_key", "")),
            model=str(d.get("model", "")),
        )

    def masked_api_key(self) -> str:
        """
        Return the api_key masked for display.

        Returns ``"tr_...wxyz"`` style (first 3 chars + last 4 chars).
        Returns ``""`` if the key is empty.
        """
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return self.api_key[0] + "***" if self.api_key else ""
        return f"{self.api_key[:3]}...{self.api_key[-4:]}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class ProviderRegistry:
    """
    Runtime provider registry.

    Loads custom providers from ``~/.openforge/secrets/providers.json`` on init,
    merges with the catalog defaults, and tracks the active provider.
    """

    def __init__(self, secrets_dir: Optional[Path] = None) -> None:
        """
        Initialize the registry.

        Args:
            secrets_dir: Override for the secrets directory (default FORGE_SECRETS_DIR).
        """
        self._secrets_dir: Path = secrets_dir or FORGE_SECRETS_DIR
        self._secrets_dir.mkdir(parents=True, exist_ok=True)
        self._secrets_file: Path = self._secrets_dir / "providers.json"
        self._active_file: Path = self._secrets_dir / "active"
        self._custom: Dict[str, StoredProviderConfig] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load custom providers + active from disk."""
        # Load providers.json.
        if self._secrets_file.exists():
            try:
                data = json.loads(self._secrets_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for name, cfg in data.items():
                        if isinstance(cfg, dict):
                            stored = StoredProviderConfig.from_dict({**cfg, "name": name})
                            self._custom[name] = stored
            except (json.JSONDecodeError, OSError, TypeError):
                self._custom = {}

    def _save(self) -> None:
        """Persist custom providers to providers.json."""
        out = {name: {k: v for k, v in cfg.to_dict().items() if k != "name"}
               for name, cfg in self._custom.items()}
        self._secrets_file.write_text(json.dumps(out, indent=2), encoding="utf-8")
        # Tighten file perms on Unix.
        if os.name == "posix":
            try:
                os.chmod(self._secrets_file, 0o600)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add(self, name: str, config: StoredProviderConfig) -> None:
        """
        Add or update a custom provider.

        Args:
            name:   Provider name.
            config: The :class:`StoredProviderConfig` to store.
        """
        self._custom[name] = config
        self._save()

    def get(self, name: str) -> Optional[StoredProviderConfig]:
        """
        Return the custom provider ``name`` (or ``None``).

        Args:
            name: Provider name.

        Returns:
            The :class:`StoredProviderConfig`, or ``None`` if unknown.
        """
        return self._custom.get(name)

    def remove(self, name: str) -> bool:
        """
        Remove a custom provider.

        Args:
            name: Provider name.

        Returns:
            ``True`` if a provider was removed, ``False`` if not found.
        """
        if name not in self._custom:
            return False
        del self._custom[name]
        self._save()
        # Clear active if it was this provider.
        if self._active_file.exists():
            try:
                if self._active_file.read_text(encoding="utf-8").strip() == name:
                    self._active_file.unlink()
            except OSError:
                pass
        return True

    def list_custom(self) -> List[StoredProviderConfig]:
        """Return all custom providers (not catalog defaults)."""
        return list(self._custom.values())

    def list_all(self) -> List[StoredProviderConfig]:
        """
        Return all providers (catalog defaults + custom), with api_key masked.

        Catalog providers have empty api_key unless the user added a custom
        entry that overrides them.
        """
        out: List[StoredProviderConfig] = []
        seen: set = set()
        # Custom first (highest precedence).
        for cfg in self._custom.values():
            masked = StoredProviderConfig(
                name=cfg.name,
                base_url=cfg.base_url,
                api_key=cfg.masked_api_key(),
                model=cfg.model,
            )
            out.append(masked)
            seen.add(cfg.name)
        # Catalog defaults (skip ones already in custom).
        for name, cat_cfg in PROVIDER_CATALOG.items():
            if name in seen:
                continue
            out.append(StoredProviderConfig(
                name=name,
                base_url=cat_cfg.base_url,
                api_key="",  # catalog entries don't expose keys
                model=cat_cfg.default_model,
            ))
        return out

    # ------------------------------------------------------------------
    # Active provider
    # ------------------------------------------------------------------
    def set_active(self, name: str) -> bool:
        """
        Mark ``name`` as the active provider.

        The provider must exist in either custom or catalog. The choice is
        persisted to ``~/.openforge/secrets/active`` so it survives restarts.

        Args:
            name: Provider name.

        Returns:
            ``True`` if set, ``False`` if the provider doesn't exist.
        """
        if name not in self._custom and name not in PROVIDER_CATALOG:
            return False
        try:
            self._active_file.write_text(name, encoding="utf-8")
        except OSError:
            pass
        return True

    def get_active(self) -> Optional[StoredProviderConfig]:
        """
        Return the active provider config (or ``None``).

        Resolution order:
            1. ``~/.openforge/secrets/active`` file.
            2. ``NEXA_PROVIDER`` env var.
            3. ``"openai"`` default.

        <VERSION>:
            The ``base_url`` is normalized so callers always receive a canonical
            OpenAI-compatible endpoint (``/v1/chat/completions`` fallback).
        """
        name: Optional[str] = None
        # Try the active file first.
        if self._active_file.exists():
            try:
                name = self._active_file.read_text(encoding="utf-8").strip() or None
            except OSError:
                name = None
        # Fall back to env.
        if not name:
            name = os.environ.get("NEXA_PROVIDER") or "openai"

        # Pull the config (custom first, then catalog).
        if name in self._custom:
            cfg = self._custom[name]
        elif name in PROVIDER_CATALOG:
            base_url, model, api_key = resolve_provider(name)
            cfg = StoredProviderConfig(
                name=name, base_url=base_url, api_key=api_key, model=model
            )
        else:
            base_url, model, api_key = resolve_provider("openai")
            cfg = StoredProviderConfig(
                name="openai", base_url=base_url, api_key=api_key, model=model
            )

        # Auto-normalize base_url → OpenAI-compatible form.
        bu = (cfg.base_url or "").strip().rstrip("/")
        if bu:
            if bu.endswith("/v"):  # TokenRouter edge case: /v → /v1
                cfg.base_url = bu + "1"
            elif "/v1" not in bu:  # plain host → append /v1
                cfg.base_url = bu + "/v1"
        return cfg

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    async def test(self, name: str) -> bool:
        """
        Probe a provider's health endpoint.

        Args:
            name: Provider name (custom or catalog).

        Returns:
            ``True`` if the provider responded with 200, else ``False``.
        """
        cfg = self._custom.get(name)
        if cfg is None and name in PROVIDER_CATALOG:
            base_url, _model, api_key = resolve_provider(name)
            cfg = StoredProviderConfig(
                name=name, base_url=base_url, api_key=api_key, model=_model
            )
        if cfg is None:
            return False
        healthy, _latency = await check_provider_health(
            cfg.base_url, api_key=cfg.api_key
        )
        return healthy
