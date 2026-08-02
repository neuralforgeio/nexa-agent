"""
Nexa Agent — Knowledge Cache
===========================

A lightweight on-disk cache for facts the agent learns from the web.
The cache avoids redundant web searches for the same entity and gives
the autonomous learner a place to persist what it has discovered.

Storage format: one JSON file per entity under ``~/.nexa/knowledge/``.
Each entry stores the summary, source, confidence, and a TTL.

The cache is intentionally **dependency-free** (stdlib only) so it works
in any environment without extra packages.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default TTL for cached facts (7 days).
DEFAULT_TTL_SECONDS: int = 7 * 24 * 3600

# Max entities to keep (LRU eviction).
DEFAULT_MAX_ENTRIES: int = 500


@dataclass
class CachedFact:
    """
    A single cached fact.

    Attributes:
        entity:     The canonical entity name (lowercased).
        summary:    Short summary text.
        source_url: Best source URL.
        source_title: Source page title.
        confidence: 0.0–1.0.
        learned_at: Unix timestamp.
        ttl_seconds:Time-to-live (fact expires after this).
        hits:       Number of cache hits.
    """

    entity: str
    summary: str
    source_url: str = ""
    source_title: str = ""
    confidence: float = 0.5
    learned_at: float = field(default_factory=time.time)
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Return ``True`` if the fact's TTL has elapsed."""
        return (time.time() - self.learned_at) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return asdict(self)


def _normalize_entity(entity: str) -> str:
    """Lowercase and strip non-alphanumeric (keep spaces)."""
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", "", entity).strip().lower()
    # Collapse spaces to single underscores for the filename.
    return cleaned.replace(" ", "_") if cleaned else "unknown"


class KnowledgeCache:
    """
    On-disk JSON cache of learned facts.

    One file per entity under ``cache_dir``. The cache is safe to read
    and write from a single process; concurrent multi-process writers
    should serialize externally.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        """
        Initialize the cache.

        Args:
            cache_dir:   Directory for cache files (default ``~/.nexa/knowledge``).
            ttl_seconds: Default TTL for new entries.
            max_entries: Soft cap on entries (LRU eviction).
        """
        self.cache_dir: Path = cache_dir or (
            Path(os.environ.get("NEXA_HOME", Path.home() / ".nexa")) / "knowledge"
        )
        self.ttl_seconds: int = ttl_seconds
        self.max_entries: int = max_entries
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _path_for(self, entity: str) -> Path:
        """Return the JSON path for ``entity``."""
        return self.cache_dir / f"{_normalize_entity(entity)}.json"

    def _index_path(self) -> Path:
        """Return the LRU index path."""
        return self.cache_dir / "_index.json"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def store(self, fact: Any) -> None:
        """
        Store or update a fact.

        Accepts either a :class:`CachedFact`, a :class:`LearnedFact`
        (from :mod:`agent.autonomous_learner`), or a plain dict.

        Args:
            fact: The fact to store.
        """
        cached = self._coerce(fact)
        path = self._path_for(cached.entity)
        path.write_text(
            json.dumps(cached.to_dict(), indent=2), encoding="utf-8"
        )
        self._touch_index(cached.entity)

    def fetch(self, entity: str) -> Optional[CachedFact]:
        """
        Fetch a non-expired fact for ``entity``.

        Args:
            entity: The entity name (case-insensitive).

        Returns:
            A :class:`CachedFact` if a fresh one exists, else ``None``.
        """
        path = self._path_for(entity)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        fact = CachedFact(**data)
        if fact.is_expired:
            return None
        # Bump hit counter.
        fact.hits += 1
        path.write_text(json.dumps(fact.to_dict(), indent=2), encoding="utf-8")
        self._touch_index(entity)
        return fact

    def invalidate(self, entity: str) -> bool:
        """
        Delete a cached fact.

        Args:
            entity: The entity name.

        Returns:
            ``True`` if a fact was deleted, ``False`` if not present.
        """
        path = self._path_for(entity)
        if path.exists():
            path.unlink()
            self._untouch_index(entity)
            return True
        return False

    def list_all(self) -> List[CachedFact]:
        """Return all non-expired cached facts."""
        out: List[CachedFact] = []
        for path in self.cache_dir.glob("*.json"):
            if path.name == "_index.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                fact = CachedFact(**data)
            except (json.JSONDecodeError, OSError, TypeError):
                continue
            if not fact.is_expired:
                out.append(fact)
        return out

    def clear(self) -> int:
        """Delete every cached fact. Returns the number deleted."""
        n = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                path.unlink()
                n += 1
            except OSError:
                pass
        return n

    # ------------------------------------------------------------------
    # LRU index
    # ------------------------------------------------------------------
    def _touch_index(self, entity: str) -> None:
        """Mark ``entity`` as recently accessed."""
        idx = self._read_index()
        idx[entity] = time.time()
        # Evict if over capacity.
        if len(idx) > self.max_entries:
            # Sort by access time ascending; evict oldest.
            for key in sorted(idx, key=idx.get)[: len(idx) - self.max_entries]:
                idx.pop(key, None)
                p = self._path_for(key)
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
        self._write_index(idx)

    def _untouch_index(self, entity: str) -> None:
        """Remove ``entity`` from the LRU index."""
        idx = self._read_index()
        idx.pop(entity, None)
        self._write_index(idx)

    def _read_index(self) -> Dict[str, float]:
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_index(self, idx: Dict[str, float]) -> None:
        path = self._index_path()
        path.write_text(json.dumps(idx, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Coercion
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce(fact: Any) -> CachedFact:
        """Convert various fact shapes into a :class:`CachedFact`."""
        if isinstance(fact, CachedFact):
            return fact
        if isinstance(fact, dict):
            return CachedFact(**{
                k: v for k, v in fact.items()
                if k in CachedFact.__dataclass_fields__  # type: ignore[attr-defined]
            })
        # Assume it's a LearnedFact-like object with to_dict().
        if hasattr(fact, "to_dict"):
            d = fact.to_dict()
            entity = d.get("entity", "unknown")
            return CachedFact(
                entity=entity,
                summary=d.get("summary", ""),
                source_url=d.get("source_url", ""),
                source_title=d.get("source_title", ""),
                confidence=d.get("confidence", 0.5),
                learned_at=d.get("learned_at", time.time()),
            )
        raise TypeError(f"Cannot coerce {type(fact)!r} to CachedFact")
