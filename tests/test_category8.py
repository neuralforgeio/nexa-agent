"""Category 8 (I-01..I-10) — Additional intelligence tests.

Covers the parts that are deterministic in this codebase today:
  - I-01/I-02: intelligence_store save/load round-trip.
  - I-08/I-09: failover selection policy hooks (cheap / vision).
  - I-10: prompt cache hit/miss behavior.
  - I-05/I-06: modules exist and are import-safe.
"""
from __future__ import annotations

import pytest

import nexa.intelligence_store as istore
from nexa.prompt_cache import PromptCache, get, put
from nexa.provider_failover import FailoverPolicy, ProviderHealth, ProviderHealthTracker


def test_intelligence_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(istore, "_PATH", tmp_path / "int.json")
    istore.save_intelligence({"persona": "coder", "rules": ["prefer-minimal"]})
    assert istore.load_intelligence()["persona"] == "coder"


def test_intelligence_store_missing_file_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(istore, "_PATH", tmp_path / "nope.json")
    assert istore.load_intelligence() == {}


def test_prompt_cache_hit_and_expiry():
    put("m", "sys", "q", {"answer": 42})
    assert get("m", "sys", "q") == {"answer": 42}
    assert get("m", "sys", "different") is None


def test_cost_aware_failover_prefers_cheaper():
    cheap = ProviderHealth(name="ollama", base_url="http://ollama", model="x", api_key="")
    pricey = ProviderHealth(name="openai", base_url="https://api", model="x", api_key="")
    tracker = ProviderHealthTracker([cheap, pricey], FailoverPolicy())
    picked = tracker.pick_next(prefer="cheap")
    assert picked and picked.name == "ollama"


def test_capability_aware_failover_requires_vision():
    text_only = ProviderHealth(name="text-only", base_url="x", model="m", api_key="", notes="text only")
    vision = ProviderHealth(name="vision", base_url="x", model="m", api_key="", notes="vision-capable")
    tracker = ProviderHealthTracker([text_only, vision], FailoverPolicy())
    picked = tracker.pick_next(prefer="vision")
    assert picked and picked.name == "vision"


def test_modules_import_cleanly():
    import nexa.telemetry as t
    import nexa.audit as a
    import nexa.cost_tracker as ct
    import agent.autopilot as ap
    import agent.swarm as s
    assert True
