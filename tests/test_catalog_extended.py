"""
Tests for the extended provider catalog (v3.0.0) — TokenRouter + Databricks.

Verifies:
    - tokenrouter is in PROVIDER_CATALOG with correct base_url + default_model.
    - databricks is in PROVIDER_CATALOG with correct default_model.
    - resolve_provider("tokenrouter") reads TOKENROUTER_API_KEY.
    - resolve_provider("databricks") reads DATABRICKS_TOKEN.
    - resolve_provider("databricks") honors NEXA_BASE_URL override.
    - All 8 providers are listable via list_providers().

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from unittest.mock import patch

import pytest

from providers.catalog import (
    PROVIDER_CATALOG,
    ProviderConfig,
    list_providers,
    resolve_provider,
)


class TestCatalogHasNewProviders:
    """Tests that the catalog includes the v3.0.0 providers."""

    def test_tokenrouter_in_catalog(self) -> None:
        """tokenrouter must be in PROVIDER_CATALOG."""
        assert "tokenrouter" in PROVIDER_CATALOG
        cfg = PROVIDER_CATALOG["tokenrouter"]
        assert cfg.base_url == "https://api.tokenrouter.io/v1"
        assert cfg.default_model == "auto:balance"
        assert "tr_" in cfg.api_key_hint

    def test_databricks_in_catalog(self) -> None:
        """databricks must be in PROVIDER_CATALOG."""
        assert "databricks" in PROVIDER_CATALOG
        cfg = PROVIDER_CATALOG["databricks"]
        assert cfg.default_model.startswith("databricks-")
        assert "dapi" in cfg.api_key_hint or "DATABRICKS_TOKEN" in cfg.api_key_hint

    def test_list_providers_returns_twentyfour(self) -> None:
        """list_providers() must return all 24 providers (8 original + 16 new in v4.2)."""
        providers = list_providers()
        names = [p.name for p in providers]
        assert "openai" in names
        assert "ollama" in names
        assert "openrouter" in names
        assert "llamacpp" in names
        assert "lmstudio" in names
        assert "vllm" in names
        assert "tokenrouter" in names
        assert "databricks" in names
        # v4.2 additions
        assert "anthropic" in names
        assert "gemini" in names
        assert "mistral" in names
        assert "groq" in names
        assert "together" in names
        assert "fireworks" in names
        assert "deepseek" in names
        assert "xai" in names
        assert "cohere" in names
        assert "perplexity" in names
        assert "localai" in names
        assert "textgen" in names
        assert "jan" in names
        assert "koboldcpp" in names
        assert "litellm" in names
        assert "helicone" in names
        assert len(providers) == 24


class TestResolveProviderTokenRouter:
    """Tests for resolve_provider('tokenrouter')."""

    def test_reads_tokenrouter_api_key(self, monkeypatch) -> None:
        """resolve_provider('tokenrouter') reads TOKENROUTER_API_KEY."""
        monkeypatch.setenv("TOKENROUTER_API_KEY", "tr_test_key_12345")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEXA_API_KEY", raising=False)
        # Clear any system llama.cpp/Ornith config so the catalog default wins.
        monkeypatch.delenv("NEXA_MODEL", raising=False)
        monkeypatch.delenv("NEXA_BASE_URL", raising=False)
        base_url, model, api_key = resolve_provider("tokenrouter")
        assert base_url == "https://api.tokenrouter.io/v1"
        assert model == "auto:balance"
        assert api_key == "tr_test_key_12345"

    def test_honors_nexa_model_override(self, monkeypatch) -> None:
        """NEXA_MODEL overrides the default model."""
        monkeypatch.setenv("TOKENROUTER_API_KEY", "tr_test")
        monkeypatch.setenv("NEXA_MODEL", "gpt-4o")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEXA_API_KEY", raising=False)
        _, model, _ = resolve_provider("tokenrouter")
        assert model == "gpt-4o"


class TestResolveProviderDatabricks:
    """Tests for resolve_provider('databricks')."""

    def test_reads_databricks_token(self, monkeypatch) -> None:
        """resolve_provider('databricks') reads DATABRICKS_TOKEN."""
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test_token_123")
        monkeypatch.setenv("NEXA_BASE_URL", "https://my-workspace.cloud.databricks.com/serving-endpoints")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEXA_API_KEY", raising=False)
        monkeypatch.delenv("DATABRICKS_API_KEY", raising=False)
        # Clear the system NEXA_MODEL so the catalog default wins
        # (NEXA_BASE_URL is intentionally kept set above).
        monkeypatch.delenv("NEXA_MODEL", raising=False)
        base_url, model, api_key = resolve_provider("databricks")
        assert base_url == "https://my-workspace.cloud.databricks.com/serving-endpoints"
        assert model == "databricks-claude-sonnet-4-6"
        assert api_key == "dapi_test_token_123"

    def test_databricks_base_url_required_from_env(self, monkeypatch) -> None:
        """databricks has no default base_url — must come from NEXA_BASE_URL."""
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi_test")
        monkeypatch.delenv("NEXA_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEXA_API_KEY", raising=False)
        monkeypatch.delenv("DATABRICKS_API_KEY", raising=False)
        base_url, _, _ = resolve_provider("databricks")
        # Catalog has empty base_url; without NEXA_BASE_URL override, it's empty.
        assert base_url == ""
