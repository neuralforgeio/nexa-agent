"""Embeddings service — deterministic local hashing embedder.

Uses a fixed-dimension (384) token-hashing scheme so it works offline with
zero downloads; if you later add a real model, keep this as the fallback.
"""
from __future__ import annotations

import hashlib
import math
from typing import List

DIM = 384


def embed_text(text: str) -> List[float]:
    """Return a normalized 384-dim vector for ``text`` (bag-of-hashed-tokens)."""
    vec = [0.0] * DIM
    tokens = [t for t in text.lower().split() if t]
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, len(digest), 4):
            idx = int.from_bytes(digest[i : i + 2], "big") % DIM
            val = (digest[i + 2] / 255.0) * (1.0 if digest[i + 3] % 2 == 0 else -1.0)
            vec[idx] += val
    norm = math.sqrt(sum(v * v for v in vec)) or 1e-9
    return [round(v / norm, 6) for v in vec]


def embed_batch(texts: List[str]) -> List[List[float]]:
    return [embed_text(t) for t in texts]
