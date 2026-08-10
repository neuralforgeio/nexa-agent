"""Guards for v5.1.2 scope: D1 (nexa submodule shims) and D2 (update/rollback wiring).

Lightweight, offline, deterministic — no git/network mutation is exercised here.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import openforge_cli.main as cli


def test_nexa_config_shim_importable() -> None:
    """D1 / QA PARTIAL-1: from nexa.config import FORGE_HOME must work."""
    import nexa.config as nc

    assert hasattr(nc, "FORGE_HOME") and nc.FORGE_HOME is not None


def test_nexa_constants_shim_importable() -> None:
    """D1 / QA PARTIAL-1: from nexa.constants import FORGE_NAME must work."""
    import nexa.constants as ncn

    assert hasattr(ncn, "FORGE_NAME") and isinstance(ncn.FORGE_NAME, str)


def test_update_rollback_use_path_resolver_forge_lib() -> None:
    """D2: main.py must resolve FORGE_LIB via openforge.path_resolver (no missing import)."""
    src = (Path(__file__).resolve().parent.parent / "openforge_cli" / "main.py").read_text(encoding="utf-8")
    assert "from openforge.path_resolver import get_forge_lib" in src
    assert "FORGE_LIB = get_forge_lib()" in src


def test_cmd_update_and_rollback_callable() -> None:
    """Regression guard for dispatch targets (keeps QA P1-X1 class fixed)."""
    assert callable(cli._cmd_update)
    params = inspect.signature(cli._cmd_rollback).parameters
    assert "to_version" in params and "list_only" in params
