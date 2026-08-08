"""
Tests for the ProviderRegistry (v3.0.0) — runtime provider management
with secrets stored in ~/.openforge/secrets/providers.json.

Verifies:
    - FORGE_SECRETS_DIR is ~/.openforge/secrets/ with mode 0o600 (best effort).
    - ProviderRegistry loads from secrets/providers.json (empty if missing).
    - add() persists a provider config (api_key masked in list_all).
    - get_active()/set_active() round-trip works.
    - remove() deletes a provider.
    - test() runs check_provider_health() and returns bool.
    - Catalog providers (openai, ollama, etc.) are listed even without a
      secrets file (merged with catalog defaults).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from openforge.config import FORGE_HOME, FORGE_SECRETS_DIR
from openforge.provider_registry import (
    ProviderRegistry,
    StoredProviderConfig,
)


class TestSecretsDir:
    """Tests for the FORGE_SECRETS_DIR constant."""

    def test_secrets_dir_under_nexa_home(self) -> None:
        """FORGE_SECRETS_DIR must be ~/.openforge/secrets/."""
        assert FORGE_SECRETS_DIR == FORGE_HOME / "secrets"

    def test_secrets_dir_created_on_import(self) -> None:
        """FORGE_SECRETS_DIR exists after importing config."""
        assert FORGE_SECRETS_DIR.exists()
        assert FORGE_SECRETS_DIR.is_dir()


class TestProviderRegistryLoad:
    """Tests for loading the registry from disk."""

    def test_load_empty_when_file_missing(self, tmp_path: Path, monkeypatch) -> None:
        """When providers.json doesn't exist, the registry is empty (no custom)."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        custom = reg.list_custom()
        assert custom == []

    def test_load_existing_providers(self, tmp_path: Path, monkeypatch) -> None:
        """Existing providers in providers.json are loaded."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        secrets_file = tmp_path / "providers.json"
        secrets_file.write_text(json.dumps({
            "tokenrouter": {
                "base_url": "https://api.tokenrouter.io/v1",
                "api_key": "tr_test123",
                "model": "auto:balance",
            }
        }))
        reg = ProviderRegistry()
        custom = reg.list_custom()
        assert "tokenrouter" in [c.name for c in custom]

    def test_malformed_json_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        """Malformed providers.json is treated as empty (no crash)."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        (tmp_path / "providers.json").write_text("{invalid json")
        reg = ProviderRegistry()
        assert reg.list_custom() == []


class TestProviderRegistryAddGetRemove:
    """Tests for add/get/remove operations."""

    def test_add_persists_provider(self, tmp_path: Path, monkeypatch) -> None:
        """add() writes the provider to providers.json."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        reg.add("tokenrouter", StoredProviderConfig(
            name="tokenrouter",
            base_url="https://api.tokenrouter.io/v1",
            api_key="tr_test123",
            model="auto:balance",
        ))
        # File must exist.
        assert (tmp_path / "providers.json").exists()
        # Reload and verify.
        reg2 = ProviderRegistry()
        cfg = reg2.get("tokenrouter")
        assert cfg is not None
        assert cfg.api_key == "tr_test123"
        assert cfg.model == "auto:balance"

    def test_get_unknown_returns_none(self, tmp_path: Path, monkeypatch) -> None:
        """get() returns None for an unknown provider."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        assert reg.get("nonexistent") is None

    def test_remove_deletes_provider(self, tmp_path: Path, monkeypatch) -> None:
        """remove() deletes the provider from disk."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        reg.add("tokenrouter", StoredProviderConfig(
            name="tokenrouter",
            base_url="https://api.tokenrouter.io/v1",
            api_key="tr_test123",
            model="auto:balance",
        ))
        assert reg.remove("tokenrouter") is True
        assert reg.get("tokenrouter") is None

    def test_remove_unknown_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        """remove() returns False for an unknown provider."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        assert reg.remove("nonexistent") is False

    def test_list_all_includes_catalog_defaults(self, tmp_path: Path, monkeypatch) -> None:
        """list_all() merges custom + catalog providers."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        all_providers = reg.list_all()
        names = [p.name for p in all_providers]
        # Catalog defaults must be present.
        assert "openai" in names
        assert "ollama" in names

    def test_list_all_masks_api_key(self, tmp_path: Path, monkeypatch) -> None:
        """list_all() masks the api_key for display (tr_...XXXX)."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        reg.add("tokenrouter", StoredProviderConfig(
            name="tokenrouter",
            base_url="https://api.tokenrouter.io/v1",
            api_key="tr_abcdefghijklmnop",
            model="auto:balance",
        ))
        all_providers = reg.list_all()
        tr = next(p for p in all_providers if p.name == "tokenrouter")
        # The masked key must NOT contain the full secret.
        assert "abcdefghijklmnop" not in (tr.api_key or "")
        assert "tr_" in (tr.api_key or "")


class TestProviderRegistryActive:
    """Tests for active provider management."""

    def test_set_and_get_active(self, tmp_path: Path, monkeypatch) -> None:
        """set_active/get_active round-trip works."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        reg.add("tokenrouter", StoredProviderConfig(
            name="tokenrouter",
            base_url="https://api.tokenrouter.io/v1",
            api_key="tr_test123",
            model="auto:balance",
        ))
        assert reg.set_active("tokenrouter") is True
        active = reg.get_active()
        assert active is not None
        assert active.name == "tokenrouter"

    def test_set_active_unknown_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        """set_active() returns False for an unknown provider."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        assert reg.set_active("nonexistent") is False

    def test_default_active_is_from_env_or_openai(self, tmp_path: Path, monkeypatch) -> None:
        """When no active is set, the default comes from NEXA_PROVIDER or 'openai'."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        monkeypatch.delenv("NEXA_PROVIDER", raising=False)
        reg = ProviderRegistry()
        active = reg.get_active()
        assert active is not None
        assert active.name == "openai"


class TestProviderRegistryTest:
    """Tests for the provider health-check method."""

    @pytest.mark.asyncio
    async def test_test_returns_bool(self, tmp_path: Path, monkeypatch) -> None:
        """test() returns True/False based on check_provider_health."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()

        # Mock check_provider_health to return (True, 50.0).
        async def fake_check(base_url, api_key="", timeout=5.0, probe_path="/v1/models"):
            return (True, 50.0)

        with patch("openforge.provider_registry.check_provider_health", side_effect=fake_check):
            result = await reg.test("openai")
        assert result is True

    @pytest.mark.asyncio
    async def test_test_unknown_provider_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        """test() returns False for an unknown provider."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        reg = ProviderRegistry()
        result = await reg.test("nonexistent")
        assert result is False
