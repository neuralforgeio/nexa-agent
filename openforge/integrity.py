"""OpenForge — Integrity manifest (SHA256 LOCK).

Generates a deterministic SHA256 manifest for every file inside FORGE_LIB
(~/.openforge/lib/) minus the venv, and uses it to detect tampering.

Files to skip during hashing:
  - venv/ virtualenv (script/tool churn on every pip install)
  - node_modules (Node deps — content varies by platform/lockfile)
  - Image PNGs? No — we hash them (icons are part of the core).
  - .pyc build caches.

APIs:
  build_manifest(root)   → {relpath: sha256}
  write_lock(root)       → writes LOCK file with manifest
  verify(root)           → (ok, mismatches:list[str], missing:list[str], extra:list[str])
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

SKIP_DIRS = {"venv", ".venv", "node_modules", "__pycache__", ".git", ".next", "dist", "build"}
LOCK_NAME = "LOCK"
LOCK_VERSION = 1


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if SKIP_DIRS & parts:
            continue
        if path.name == LOCK_NAME:
            continue
        if path.suffix == ".pyc":
            continue
        yield path


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(128 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(root: Path) -> Dict[str, str]:
    """Build a {relpath: sha256} map under *root*.

    Raises no errors on missing files: scan is best-effort.
    """
    out: Dict[str, str] = {}
    for f in _iter_files(root):
        try:
            out[str(f.relative_to(root)).replace("\\", "/")] = _hash_file(f)
        except (OSError, PermissionError):
            continue
    return out


def manifest_payload(root: Path) -> dict:
    """Full lock payload with metadata."""
    m = build_manifest(root)
    return {
        "version": LOCK_VERSION,
        "root": str(root),
        "file_count": len(m),
        "manifest": m,
    }


def write_lock(root: Path, dest: Optional[Path] = None) -> Path:
    """Write the LOCK file next to FORGE_LIB root and return its path."""
    lock_path = dest or (root / LOCK_NAME)
    payload = manifest_payload(root)
    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        lock_path.chmod(0o444)  # best-effort on Windows
    except OSError:
        pass
    return lock_path


def verify(root: Path, lock_data: Optional[dict] = None) -> tuple[bool, List[str], List[str], List[str]]:
    """Compare current lib against the manifest.

    Returns:
        (ok, mismatches, missing, extra)
        ok == True iff no content changed, nothing is missing, and nothing extra appears.
    """
    if lock_data is None:
        lp = root / LOCK_NAME
        if not lp.exists():
            return False, [], [], []
        try:
            lock_data = json.loads(lp.read_text(encoding="utf-8"))
        except Exception:
            return False, [], [], []

    old = lock_data.get("manifest", {})
    new = build_manifest(root)

    mismatches = sorted(k for k, v in old.items() if k in new and new[k] != v)
    missing = sorted(k for k in old if k not in new)
    extra = sorted(k for k in new if k not in old)
    ok = not mismatches and not missing and not extra
    return ok, mismatches, missing, extra


__all__ = ["build_manifest", "manifest_payload", "write_lock", "verify", "LOCK_NAME", "LOCK_VERSION"]
