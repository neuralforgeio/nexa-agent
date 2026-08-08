"""Prompt/response cache — reduce duplicate LLM calls for identical prompts.

Token/PDL: keyed by (model, system, user_prompt). Cache is process-local
(in-memory) and size-capped, with a TTL; it never persists provider keys.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

_TTL = 300.0        # 5 minutes
_MAX_ENTRIES = 512


class _Entry:
    __slots__ = ("value", "expires")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.expires = time.monotonic() + _TTL


class PromptCache:
    """OrderedDict-backed LRU+TTL cache for LLM responses."""

    def __init__(self) -> None:
        self._cache: "OrderedDict[str, _Entry]" = OrderedDict()

    @staticmethod
    def _key(model: str, system: str, prompt: str) -> str:
        h = hashlib.sha256()
        h.update(model.encode("utf-8")); h.update(b"::")
        h.update(system.encode("utf-8")); h.update(b"::")
        h.update(prompt.encode("utf-8"))
        return h.hexdigest()

    def get(self, model: str, system: str, prompt: str) -> Optional[Any]:
        key = self._key(model, system, prompt)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.expires < time.monotonic():
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry.value

    def put(self, model: str, system: str, prompt: str, value: Any) -> None:
        key = self._key(model, system, prompt)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = _Entry(value)
        while len(self._cache) > _MAX_ENTRIES:
            self._cache.popitem(last=False)


_CACHE = PromptCache()


def get(model: str, system: str, prompt: str) -> Optional[Any]:
    return _CACHE.get(model, system, prompt)


def put(model: str, system: str, prompt: str, value: Any) -> None:
    _CACHE.put(model, system, prompt, value)
