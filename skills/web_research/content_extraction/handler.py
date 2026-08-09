"""
OpenForge — content_extraction skill (web_research)
=====================================================

Purpose
-------
Fetch a URL and extract structured data matching a caller-supplied
``extraction_schema``. Returns the manifest contract: ``extracted_data``
(object) and ``confidence`` (number, 0..1).

Permissions
-----------
Declared: ``network:*``.

Honesty note
------------
This handler never fabricates page content. It attempts a real GET via
``tool_api.http_client()`` with a short timeout, inside ``try/except``. On
any fetch failure — offline, unroutable host, timeout, non-2xx — it
returns ``{"extracted_data": {}, "confidence": 0.0}``: the honest
"nothing could be extracted" result, schema-valid by construction, and it
does **not** call the model with empty/garbage content. Only a real,
successfully fetched page body is handed to the model, which is asked to
extract exactly the fields named in ``extraction_schema`` and mark
unfound fields as ``null`` rather than guess. LLM and JSON-parse errors
(after a successful fetch) propagate to the caller.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent import tool_api
from skills._common import ask_llm_json, coerce_number, coerce_str, require

__all__ = ["handle", "SYSTEM"]

_FETCH_TIMEOUT = 5.0  # short, best-effort; hermetic tests fail fast
_MAX_PAGE_CHARS = 8000  # cap what we hand to the model

SYSTEM = (
    "You are the content_extraction skill inside the Nexa Agent skills "
    "system. You are given a real fetched web page body and a caller-supplied "
    "extraction schema mapping field names to expected types. Extract ONLY "
    "what is genuinely present in the page text. Respond with a single JSON "
    "object and nothing else — no prose, no markdown fence. The object MUST "
    "have these keys:\n"
    '  "extracted_data": object — exactly the fields named in the extraction '
    "schema, populated from the page where genuinely present; use null for "
    "any field not found in the page. NEVER invent values;\n"
    '  "confidence": number from 0.0 to 1.0 — how confidently the schema was '
    "satisfied from the real page content (0.0 when nothing could be "
    "extracted)."
)


async def _fetch_page(url: str) -> Optional[str]:
    """
    Best-effort GET of ``url``. Returns the page text on an HTTP < 400
    success with a non-empty body, otherwise None. Never raises — every
    failure mode (offline, unroutable, timeout, junk) degrades to None.
    """
    try:
        client = tool_api.http_client(timeout=_FETCH_TIMEOUT)
        try:
            resp = await client.get(url)
            if getattr(resp, "status_code", 0) >= 400:
                return None
            text = coerce_str(getattr(resp, "text", ""))
        finally:
            aclose = getattr(client, "aclose", None)
            if callable(aclose):
                res = aclose()
                if hasattr(res, "__await__"):
                    await res
    except Exception:
        return None
    text = text.strip()
    return text if text else None


def _build_prompt(url: str, extraction_schema: Dict[str, Any], page: str) -> str:
    import json

    lines = [
        f"Source URL: {url}",
        "Extraction schema (field name -> expected type):",
        json.dumps(extraction_schema, indent=2, default=str),
        "",
        "Page body (real fetched content, verbatim excerpt):",
        page[:_MAX_PAGE_CHARS],
    ]
    return "\n".join(lines)


async def handle(input_data: dict, provider) -> dict:
    """
    Fetch ``input_data['url']`` and extract per ``extraction_schema``.

    Raises:
        SkillInputError: Missing/wrongly-typed ``url`` or ``extraction_schema``.
        RuntimeError:    The provider signalled an LLM error (after a
            successful fetch; never swallowed).
        ValueError:      The model reply contained no parseable JSON object
            (after a successful fetch).

    On fetch failure returns the honest degraded payload
    ``{"extracted_data": {}, "confidence": 0.0}`` instead of raising.
    """
    url = require(input_data, "url", str, "URL to fetch")
    extraction_schema = require(
        input_data, "extraction_schema", dict, "extraction schema"
    )

    page = await _fetch_page(url)
    if page is None:
        # Honest offline/degraded result: nothing was fetched, so nothing is
        # extracted and the model is NOT asked to hallucinate from nothing.
        return {"extracted_data": {}, "confidence": 0.0}

    prompt = _build_prompt(url, extraction_schema, page)
    data = await ask_llm_json(provider, prompt, system=SYSTEM)

    extracted = data.get("extracted_data")
    if not isinstance(extracted, dict):
        # The model extracted nothing it would stand behind — honest default,
        # not a fabrication.
        extracted = {}

    confidence = coerce_number(data.get("confidence"), default=0.0)
    confidence = max(0.0, min(1.0, confidence))

    return {"extracted_data": extracted, "confidence": confidence}
