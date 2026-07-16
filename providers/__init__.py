"""
Nexa Agent — Providers Package
==============================

This package contains provider adapters for various LLM backends:
OpenAI, Ollama, llama.cpp, OpenRouter, and any OpenAI-compatible endpoint.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from .catalog import PROVIDER_CATALOG, resolve_provider, list_providers

__all__ = ["PROVIDER_CATALOG", "resolve_provider", "list_providers"]
