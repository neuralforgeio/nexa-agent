"""
Nexa Agent — Provider Catalog & Resolution
==========================================

This module defines a catalog of known LLM providers and a resolver that
returns the correct ``base_url`` and default model for a given provider name.

Supported providers:
    - openai      (default, https://api.openai.com/v1)
    - openrouter  (https://openrouter.ai/api/v1)
    - ollama      (http://localhost:11434/v1)
    - llamacpp    (http://localhost:8080/v1)
    - lmstudio    (http://localhost:1234/v1)
    - vllm        (http://localhost:8000/v1)
    - custom      (user-supplied NEXA_BASE_URL)

Any OpenAI-compatible endpoint works — set ``NEXA_BASE_URL`` and
``NEXA_MODEL`` environment variables.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ProviderConfig:
    """
    Configuration for a single LLM provider.

    Attributes:
        name:          The friendly provider name (e.g. ``"ollama"``).
        base_url:      The OpenAI-compatible API base URL.
        default_model: A sensible default model for this provider.
        api_key_hint:  A hint about the API key (some local providers
                       accept any non-empty string).
        description:   A short human-readable description.
    """

    name: str
    base_url: str
    default_model: str
    api_key_hint: str
    description: str


#: The catalog of known providers. Keys are lowercase provider names.
PROVIDER_CATALOG: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        api_key_hint="Requires OPENAI_API_KEY",
        description="OpenAI official API (GPT-4o, GPT-4o-mini, etc.)",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="anthropic/claude-3.5-sonnet",
        api_key_hint="Requires OPENROUTER_API_KEY",
        description="OpenRouter — access 100+ models with one key",
    ),
    "ollama": ProviderConfig(
        name="ollama",
        base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        api_key_hint="Any non-empty string (e.g. 'ollama')",
        description="Ollama — run models locally (llama3.2, qwen2.5, mistral)",
    ),
    "llamacpp": ProviderConfig(
        name="llamacpp",
        base_url="http://localhost:8080/v1",
        default_model="Ornith-1.0-9b-Q4_K_M.gguf",
        api_key_hint="Any non-empty string",
        description="llama.cpp server (llama-server --port 8080)",
    ),
    "lmstudio": ProviderConfig(
        name="lmstudio",
        base_url="http://localhost:1234/v1",
        default_model="loaded-model",
        api_key_hint="Any non-empty string",
        description="LM Studio local server",
    ),
    "vllm": ProviderConfig(
        name="vllm",
        base_url="http://localhost:8000/v1",
        default_model="meta-llama/Llama-3.1-8B-Instruct",
        api_key_hint="Any non-empty string",
        description="vLLM inference server",
    ),
    "tokenrouter": ProviderConfig(
        name="tokenrouter",
        base_url="https://api.tokenrouter.io/v1",
        default_model="auto:balance",
        api_key_hint="Requires TOKENROUTER_API_KEY (key prefix tr_)",
        description=(
            "TokenRouter — OpenAI-compatible LLM routing gateway. "
            "Model can be a routing mode (auto:balance/cost/quality/latency) "
            "or a pinned model (gpt-4o, claude-3-7-sonnet-latest:quality, "
            "anthropic:claude-3-5-sonnet, gemini:..., mistral:..., deepseek:...)."
        ),
    ),
    "databricks": ProviderConfig(
        name="databricks",
        base_url="",  # user must override via NEXA_BASE_URL (workspace host)
        default_model="databricks-claude-sonnet-4-6",
        api_key_hint="Requires DATABRICKS_TOKEN (PAT, prefix dapi); also set NEXA_BASE_URL=<workspace>/serving-endpoints",
        description=(
            "Databricks Foundation Model APIs / AI Gateway (OpenAI-compatible). "
            "Set NEXA_BASE_URL to https://<workspace-host>/serving-endpoints and "
            "DATABRICKS_TOKEN to your PAT. Models: databricks-claude-sonnet-*, "
            "databricks-gpt-oss-*, databricks-meta-llama-*, etc."
        ),
    ),
}


def list_providers() -> List[ProviderConfig]:
    """
    Return all known providers as a list.

    Returns:
        A list of :class:`ProviderConfig` instances.
    """
    return list(PROVIDER_CATALOG.values())


def resolve_provider(
    name: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Resolve the (base_url, model, api_key) tuple for a provider.

    Resolution order:
        1. If ``name`` is given and exists in the catalog, use it.
        2. Else if ``NEXA_PROVIDER`` env var is set, use it.
        3. Else if ``NEXA_BASE_URL`` env var is set, use it directly (custom).
        4. Else default to ``"openai"``.

    The API key is resolved from ``OPENAI_API_KEY`` (or the provider-specific
    env var). For local providers (ollama, llamacpp, lmstudio, vllm), a
    dummy key is used if none is set.

    Args:
        name: Optional provider name (e.g. ``"ollama"``).

    Returns:
        A tuple of ``(base_url, model, api_key)``.
    """
    # Determine the provider name.
    if name is None:
        name = os.environ.get("NEXA_PROVIDER", "").lower()
    if not name:
        # If NEXA_BASE_URL is set, treat as custom provider.
        if os.environ.get("NEXA_BASE_URL"):
            name = "custom"
        else:
            name = "openai"

    # Custom provider via env var.
    if name == "custom":
        base_url = os.environ.get("NEXA_BASE_URL", "")
        model = os.environ.get("NEXA_MODEL", "gpt-4o")
        api_key = os.environ.get("OPENAI_API_KEY", os.environ.get("NEXA_API_KEY", "dummy"))
        return base_url, model, api_key

    # Known provider from catalog.
    config = PROVIDER_CATALOG.get(name, PROVIDER_CATALOG["openai"])

    # Allow env override of base_url and model.
    base_url = os.environ.get("NEXA_BASE_URL", config.base_url)
    model = os.environ.get("NEXA_MODEL", config.default_model)

    # Resolve API key.
    # Resolution order:
    #   1. OPENAI_API_KEY (universal fallback)
    #   2. NEXA_API_KEY (universal fallback)
    #   3. <NAME>_API_KEY (e.g. TOKENROUTER_API_KEY, OPENROUTER_API_KEY)
    #   4. Provider-specific token env vars (DATABRICKS_TOKEN for databricks).
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("NEXA_API_KEY")
        or os.environ.get(f"{name.upper()}_API_KEY")
        or ""
    )
    # v3.0.0: provider-specific token env vars.
    if not api_key and name == "databricks":
        api_key = os.environ.get("DATABRICKS_TOKEN", "")
    # Local providers accept any non-empty key.
    if not api_key and config.name in ("ollama", "llamacpp", "lmstudio", "vllm"):
        api_key = "dummy"

    return base_url, model, api_key
