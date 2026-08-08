"""Regression test for provider base_url normalization. (RCA)"""
from openforge.provider_registry import ProviderRegistry, StoredProviderConfig
from openforge.provider import LLMProvider  # instantiation check only


def test_active_provider_base_url_is_normalized(tmp_path, monkeypatch):
    import os
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "providers.json").write_text(
        '{"tokenrouter": {"base_url": "https://api.tokenrouter.com/v", "api_key": "sk-x", "model": "m"}}',
        encoding="utf-8",
    )
    (secrets / "active").write_text("tokenrouter", encoding="utf-8")
    reg = ProviderRegistry(secrets_dir=secrets)
    getattr(reg, "_secrets_dir")
    monkeypatch.setenv("FORGE_HOME", str(tmp_path))
    # Load custom manually to simulate re-load post-write.
    import importlib
    importlib.reload(__import__("openforge.config", fromlist=["*"]))
    cfg = reg.get_active()
    assert cfg is not None and cfg.name == "tokenrouter"
    assert cfg.base_url.endswith("/v1")


def test_llmprovider_from_active_uses_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_PROVIDER", "tokenrouter")
    import importlib, os
    import openforge.provider as p
    importlib.reload(p)
    prov = p.LLMProvider.from_active_provider()
    assert prov.base_url.endswith("/v1")  # normalization landed
