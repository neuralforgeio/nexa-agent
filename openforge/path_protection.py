"""OpenForge — Path Protection.

Read-only enforcement for the FORGE_LIB (~/.openforge/lib) core.

Tools that write or delete files MUST call ensure_safe_write(path) BEFORE
touching the filesystem. Operations targeting any path inside FORGE_LIB are
rejected with a hard error so the agent cannot accidentally rewrite its own
code at runtime.

Rules:
- reads inside lib/ are allowed.
- writes/deletes/renames inside lib/ are REJECTED.
- paths outside lib/ pass through unchanged (nothing to protect).
"""
from __future__ import annotations

from pathlib import Path

from openforge.path_resolver import get_forge_lib, is_core_path


class ReadOnlyViolation(PermissionError):
    """Raised when a write targets the read-only OpenForge core."""


def assert_no_core_write(target: Path | str, operation: str) -> None:
    """Raise ReadOnlyViolation if *target* is inside the protected core.

    Args:
        target:    Path the caller intends to modify.
        operation: Human-readable verb describing the operation (e.g. "write").

    Raises:
        ReadOnlyViolation: when the target resolves into FORGE_LIB.
    """
    if not is_core_path(target):
        return
    lib = get_forge_lib()
    raise ReadOnlyViolation(
        f"OpenForge core is read-only: cannot {operation} '{target}'. "
        f"All paths under FORGE_LIB ({lib}) are protected. "
        "Use FORGE_WORKSPACE or a user folder instead, or run `openforge update`."
    )


def ensure_safe_write(target: Path | str, operation: str) -> None:
    """Guard helper used by tools: no-op when safe, raise when target is core."""
    assert_no_core_write(target, operation)


__all__ = ["assert_no_core_write", "ensure_safe_write", "ReadOnlyViolation"]
