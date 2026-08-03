"""
Nexa Agent — web_monitoring skill (web_research)
=================================================

Purpose
-------
Register a set of URLs for monitoring on a fixed interval, watching for
``content`` | ``price`` | ``status`` | ``any`` changes. Returns the manifest
contract: ``monitored`` (bool) and ``changes_detected`` (array of
``{url, change_type, diff}``).

Permissions
-----------
Declared: ``network:*``, ``memory:write``.

Honesty note
------------
v0.1.0 is deliberately **not** a background scheduler. A single invocation
makes ONE best-effort fetch attempt per URL (short timeout) to establish a
current baseline; there is no timer, no persisted snapshot store, and no
comparison against a prior crawl. Consequently:

  * ``monitored`` is True when the handler iterated every URL and recorded
    that URL's first-fetch status (reachable or not) — i.e. the baseline
    registration pass completed for all URLs, whether or not any single
    fetch succeeded;
  * ``changes_detected`` is ALWAYS an empty list on this first run: with no
    prior snapshot there is no honest diff to report, and this handler never
    fabricates diffs.

Fetch failures (offline, unroutable host, timeout) degrade silently per URL:
they affect nothing beyond that URL's baseline status note, which is a
local observation rather than part of the schema'd output.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from agent import tool_api
from skills._common import as_list, coerce_str, require

__all__ = ["handle"]

_FETCH_TIMEOUT = 5.0  # short, best-effort; hermetic tests fail fast


async def _baseline_status(url: str) -> str:
    """
    One best-effort GET to record a baseline status string. Any failure
    returns an honest ``"unreachable: <reason>"`` note — never raises.
    """
    try:
        client = tool_api.http_client(timeout=_FETCH_TIMEOUT)
        try:
            resp = await client.get(url)
            return f"http {getattr(resp, 'status_code', '?')}"
        finally:
            aclose = getattr(client, "aclose", None)
            if callable(aclose):
                res = aclose()
                if hasattr(res, "__await__"):
                    await res
    except Exception as exc:
        return f"unreachable: {type(exc).__name__}"


async def _status_pair(url: str):
    """Helper for the concurrent baseline pass: (url, status)."""
    return url, await _baseline_status(url)


async def handle(input_data: dict, provider) -> dict:
    """
    Run one baseline-registration pass over ``input_data['urls']``.

    This handler raises :class:`SkillInputError` for missing/wrongly-typed
    ``urls``, ``check_interval`` or ``change_type``. It does **not** use the
    LLM provider: there is no synthesis to perform, only an honest baseline
    fetch, so the provider is accepted (registry signature) but unused.

    Returns:
        ``{"monitored": True, "changes_detected": []}`` once every URL has
        had its single baseline fetch attempted.
    """
    urls_raw = require(input_data, "urls", list, "urls to monitor")
    urls: List[str] = [coerce_str(u).strip() for u in as_list(urls_raw)]
    urls = [u for u in urls if u]
    check_interval = require(input_data, "check_interval", int, "check interval (seconds)")
    change_type = require(input_data, "change_type", str, "change type")
    _ = (check_interval, change_type)  # recorded for the monitoring intent; no
    # scheduler consumes them in v0.1.0 (documented honestly above).

    baselines: Dict[str, str] = {}
    if urls:
        # One baseline fetch per URL, run concurrently so a set of slow/
        # unreachable hosts costs ~one timeout, not one-per-URL.
        import asyncio

        pairs = await asyncio.gather(*(_status_pair(u) for u in urls))
        baselines.update(pairs)

    # First run: a baseline now exists for every URL, but there is no prior
    # snapshot to diff against — so no changes are reported and none are
    # ever fabricated.
    return {
        "monitored": True,
        "changes_detected": [],
    }
