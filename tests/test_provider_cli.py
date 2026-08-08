"""
Tests for the `nexa provider` CLI subcommands (v3.0.0).

Verifies:
    - `nexa provider list` shows all 8 providers (catalog + custom).
    - `nexa provider add` with --base-url --api-key --model flags (non-interactive).
    - `nexa provider use` activates a provider.
    - `nexa provider remove` deletes a provider.
    - `nexa provider add` interactive (mocked stdin) prompts for missing fields.
    - `nexa provider test` runs the health check.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import io
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from openforge_cli.main import main, _cmd_provider


class TestProviderList:
    """Tests for `nexa provider list`."""

    def test_list_shows_eight_providers(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """`nexa provider list` shows all 8 catalog providers."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        rc = main(["provider", "list"])
        assert rc == 0
        captured = capsys.readouterr()
        # All 8 catalog providers must appear.
        for name in ("openai", "openrouter", "ollama", "llamacpp",
                     "lmstudio", "vllm", "tokenrouter", "databricks"):
            assert name in captured.out


class TestProviderAddNonInteractive:
    """Tests for `nexa provider add` with flag overrides (no stdin)."""

    def test_add_with_flags_persists(self, tmp_path: Path, monkeypatch) -> None:
        """--base-url --api-key --model flags skip interactive prompts."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        rc = main([
            "provider", "add", "tokenrouter",
            "--base-url", "https://api.tokenrouter.io/v1",
            "--api-key", "tr_test123",
            "--model", "auto:balance",
        ])
        assert rc == 0
        # Verify persisted.
        from openforge.provider_registry import ProviderRegistry
        reg = ProviderRegistry()
        cfg = reg.get("tokenrouter")
        assert cfg is not None
        assert cfg.api_key == "tr_test123"
        assert cfg.model == "auto:balance"

    def test_add_custom_provider(self, tmp_path: Path, monkeypatch) -> None:
        """A fully custom provider (not in catalog) can be added."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        rc = main([
            "provider", "add", "my-custom-llm",
            "--base-url", "https://my-llm.example.com/v1",
            "--api-key", "sk-mykey",
            "--model", "my-model-v1",
        ])
        assert rc == 0
        from openforge.provider_registry import ProviderRegistry
        reg = ProviderRegistry()
        cfg = reg.get("my-custom-llm")
        assert cfg is not None
        assert cfg.base_url == "https://my-llm.example.com/v1"


class TestProviderUse:
    """Tests for `nexa provider use`."""

    def test_use_activates_provider(self, tmp_path: Path, monkeypatch) -> None:
        """`nexa provider use <name>` sets the active provider."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        # First add a provider.
        main([
            "provider", "add", "tokenrouter",
            "--base-url", "https://api.tokenrouter.io/v1",
            "--api-key", "tr_test123",
            "--model", "auto:balance",
        ])
        # Then use it.
        rc = main(["provider", "use", "tokenrouter"])
        assert rc == 0
        from openforge.provider_registry import ProviderRegistry
        reg = ProviderRegistry()
        active = reg.get_active()
        assert active is not None
        assert active.name == "tokenrouter"

    def test_use_unknown_returns_error(self, tmp_path: Path, monkeypatch) -> None:
        """`nexa provider use <unknown>` returns exit code 1."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        rc = main(["provider", "use", "nonexistent"])
        assert rc == 1


class TestProviderRemove:
    """Tests for `nexa provider remove`."""

    def test_remove_deletes_provider(self, tmp_path: Path, monkeypatch) -> None:
        """`nexa provider remove <name>` deletes the provider."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        main([
            "provider", "add", "tokenrouter",
            "--base-url", "https://api.tokenrouter.io/v1",
            "--api-key", "tr_test123",
            "--model", "auto:balance",
        ])
        rc = main(["provider", "remove", "tokenrouter"])
        assert rc == 0
        from openforge.provider_registry import ProviderRegistry
        reg = ProviderRegistry()
        assert reg.get("tokenrouter") is None

    def test_remove_unknown_returns_error(self, tmp_path: Path, monkeypatch) -> None:
        """`nexa provider remove <unknown>` returns exit code 1."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        rc = main(["provider", "remove", "nonexistent"])
        assert rc == 1


class TestProviderTest:
    """Tests for `nexa provider test`."""

    def test_test_returns_zero_when_healthy(self, tmp_path: Path, monkeypatch) -> None:
        """`nexa provider test <name>` returns 0 when the provider is healthy."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)

        async def fake_test(self, name):
            return True

        with patch("openforge.provider_registry.ProviderRegistry.test", fake_test):
            rc = main(["provider", "test", "openai"])
        assert rc == 0

    def test_test_returns_one_when_unhealthy(self, tmp_path: Path, monkeypatch) -> None:
        """`nexa provider test <name>` returns 1 when unhealthy."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)

        async def fake_test(self, name):
            return False

        with patch("openforge.provider_registry.ProviderRegistry.test", fake_test):
            rc = main(["provider", "test", "openai"])
        assert rc == 1


class TestProviderAddInteractive:
    """Tests for `nexa provider add` with interactive prompts (mocked stdin)."""

    def test_add_interactive_prompts(self, tmp_path: Path, monkeypatch) -> None:
        """Interactive add prompts for name, api_key, model."""
        monkeypatch.setattr("openforge.provider_registry.FORGE_SECRETS_DIR", tmp_path)
        # Mock input() and getpass.getpass().
        inputs = iter(["tokenrouter", "", "auto:balance"])  # name, base_url (empty=use default), model
        monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
        monkeypatch.setattr("getpass.getpass", lambda *a, **kw: "tr_interactive_key")
        rc = main(["provider", "add"])
        assert rc == 0
        from openforge.provider_registry import ProviderRegistry
        reg = ProviderRegistry()
        cfg = reg.get("tokenrouter")
        assert cfg is not None
        assert cfg.api_key == "tr_interactive_key"
