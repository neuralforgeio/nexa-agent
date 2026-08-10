"""Regression tests for the openforge_cli dispatch table.

Guards the defects found in QA-VERIFY-v503 group no. 1:
- P1-X1  : `_cmd_update` / `_cmd_rollback` were dispatched but undefined -> NameError.
- P0-4   : `openforge doctor` was absent from the dispatch table -> printed help banner.
- P1-15  : `_cmd_doctor` was defined twice (second definition shadowed the first).
- P0-2/X2: install.sh symlink loop dropped `openforge-gateway`.

These are structural/behavioral guard tests: they assert the dispatch wiring exists and
that each advertised CLI subcommand maps to a real, single callable — without executing
the networked/gateway side effects.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import openforge_cli.main as cli


REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = REPO_ROOT / "openforge_cli" / "main.py"
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"


def test_cmd_update_is_defined_and_callable() -> None:
    """P1-X1: `openforge update` must not raise NameError."""
    assert callable(getattr(cli, "_cmd_update", None)), "_cmd_update is not defined/callable"
    sig = inspect.signature(cli._cmd_update)
    assert len(sig.parameters) == 0, "_cmd_update must be callable with no args"


def test_cmd_rollback_is_defined_and_callable() -> None:
    """P1-X1: `openforge rollback` must not raise NameError; flags must match parser."""
    assert callable(getattr(cli, "_cmd_rollback", None)), "_cmd_rollback is not defined/callable"
    params = inspect.signature(cli._cmd_rollback).parameters
    assert "to_version" in params and "list_only" in params, (
        "_cmd_rollback signature must accept to_version/list_only (parser wires --to/--list)"
    )


def test_cmd_doctor_is_defined_exactly_once_and_dispatched() -> None:
    """P0-4 + P1-15: one canonical _cmd_doctor, and the dispatch table routes 'doctor'."""
    src = MAIN_PY.read_text(encoding="utf-8")
    # exactly one definition survives
    assert len(re.findall(r"^def _cmd_doctor\(", src, flags=re.M)) == 1, (
        "expected exactly one 'def _cmd_doctor' in openforge_cli/main.py"
    )
    # dispatch table routes the 'doctor' subcommand
    assert re.search(r'elif\s+args\.command\s*==\s*"doctor"', src), (
        "dispatch table is missing 'elif args.command == \"doctor\":'"
    )
    assert callable(getattr(cli, "_cmd_doctor", None)), "_cmd_doctor is not defined/callable"


def test_install_sh_symlinks_all_five_binaries() -> None:
    """P0-2 (regression): install.sh must link all five entry points.

    Specifically guards against the v5.0.3 regression that dropped openforge-gateway.
    """
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(r"for\s+b\s+in\s+([^;]+);", text)
    assert m, "could not locate the install.sh symlink loop ('for b in ...')"
    loop_items = m.group(1).split()
    for expected in ("openforge", "openforge-chat", "openforge-agent", "openforge-gateway", "openforge-tui"):
        assert expected in loop_items, f"install.sh symlink loop is missing '{expected}'"


def test_help_table_lists_update_rollback_migrate() -> None:
    """Help surface must list update/rollback/migrate alongside doctor (consistency)."""
    src = MAIN_PY.read_text(encoding="utf-8")
    for cmd in ("update", "rollback", "migrate", "doctor"):
        assert f'("{cmd}"' in src, f"_print_rich_help table is missing a row for '{cmd}'"
