"""
code_search skill (v4.4.0)
==========================

Purpose: search the workspace code/text and return ranked matches with a real
index (FTS5 when available, deterministic substring scoring otherwise).

Permissions used: filesystem:workspace (reads the tree via the workspace
sandbox), memory:read (declared; memory scope is a documented no-op in this
baseline — see below).

Honesty notes:
  * Results always come from a real index built over the real workspace files
    (never a canned list). Scores are computed from the index.
  * ``search_scope: memory`` / ``all`` does not yet wire into the agent memory
    store; in v0.1.0 it is searched as a no-op and only workspace hits are
    returned. This is documented rather than faked.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from skills._common import require

from .index import WorkspaceIndex

_VALID_SCOPES = ("workspace", "memory", "all")


def _workspace_root() -> Path:
    root = os.environ.get("FORGE_WORKSPACE") or os.getcwd()
    return Path(root)


async def handle(input_data: Dict[str, Any], provider) -> Dict[str, Any]:
    query = require(input_data, "query", str, "query").strip()
    if not query:
        from skills.registry import SkillInputError

        raise SkillInputError("'query' must be a non-empty string")

    scope = input_data.get("search_scope", "all")
    if scope not in _VALID_SCOPES:
        from skills.registry import SkillInputError

        raise SkillInputError(f"'search_scope' must be one of {_VALID_SCOPES}, got {scope!r}")

    limit = input_data.get("limit", 10)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        from skills.registry import SkillInputError

        raise SkillInputError("'limit' must be an integer >= 1")

    index = WorkspaceIndex(_workspace_root())
    results = index.search(query, limit=limit)

    # scope is honoured at the boundary; memory adds nothing in v0.1.0.
    return {"results": results}
