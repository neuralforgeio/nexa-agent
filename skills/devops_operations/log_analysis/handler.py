"""
Skill: log_analysis
===================

Analyse REAL log text read from a workspace file for anomalies, recurring
patterns, a root-cause hypothesis, and remediation recommendations, tuned to
the requested ``analysis_type`` (``anomaly`` | ``pattern`` | ``error`` |
``security``).

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``log_source`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``.
  * ``memory:read`` — declared by the manifest; this handler itself does not
    touch memory.

Honesty note: every anomaly, pattern, the root cause, and all
recommendations come from the model's reply to a prompt that embeds the
ACTUAL log bytes read from disk — nothing here is stubbed or pre-canned.
If the model's reply is not parseable JSON, ``ValueError`` propagates rather
than fabricating findings about logs nobody analysed.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent import tool_api
from skills._common import ask_llm_json, as_list, coerce_number, coerce_str  # noqa: F401
from skills._common import require
from skills.registry import SkillInputError

__all__ = ["handle"]

_ANALYSIS_TYPES = ("anomaly", "pattern", "error", "security")
_MAX_LOG_CHARS = 32_000  # keep prompts bounded on huge files

SYSTEM = (
    "You are Forge's log-analysis engine. You are given the REAL contents of "
    "a log file together with its declared format and a requested analysis "
    "type (anomaly | pattern | error | security). Analyse ONLY the log lines "
    "actually shown — never invent log entries, timestamps, error codes, or "
    "root causes that are not grounded in the shown text. Respond with a "
    "SINGLE JSON object, and nothing else (no markdown fences, no prose "
    "around it), with exactly these keys:\n"
    '  "anomalies": an array of objects, each with keys "line" (integer '
    "1-based line number, or 0 if not tied to a line) and \"description\" "
    "(string). Use an empty array if nothing anomalous is present.\n"
    '  "patterns": an array of short strings describing recurring entries '
    "genuinely repeated in the shown log (empty array if none).\n"
    '  "root_cause": a string with your best root-cause hypothesis grounded '
    'in the shown lines; use "insufficient evidence in the shown log" if '
    "you cannot justify one.\n"
    '  "recommendations": an array of actionable strings (empty array if '
    "none are warranted)."
)


def _read_log(log_source: str) -> str:
    """Resolve ``log_source`` inside the workspace and read it as text."""
    try:
        p = tool_api.workspace_path(log_source)
    except ValueError as exc:
        raise SkillInputError(f"invalid log_source {log_source!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"log_source {log_source!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )
    return p.read_text(encoding="utf-8", errors="replace")


def _normalise_anomaly(item: Any) -> Dict[str, Any]:
    """Map a raw model anomaly to {line:int, description:str}."""
    if isinstance(item, dict):
        line = item.get("line")
        try:
            line = int(line) if line is not None and not isinstance(line, bool) else 0
        except (TypeError, ValueError):
            line = 0
        return {"line": line, "description": coerce_str(item.get("description"))}
    return {"line": 0, "description": coerce_str(item)}


async def handle(input_data: dict, provider) -> dict:
    """Read a real log file, analyse it via the model, return findings."""
    log_source = require(input_data, "log_source", str, "workspace log file")
    log_format = require(input_data, "log_format", str, "log format")
    analysis_type = require(input_data, "analysis_type", str, "analysis type")
    if analysis_type not in _ANALYSIS_TYPES:
        raise SkillInputError(
            f"analysis_type must be one of {sorted(_ANALYSIS_TYPES)}, got "
            f"{analysis_type!r}"
        )

    log_text = _read_log(log_source)
    truncated = len(log_text) > _MAX_LOG_CHARS
    shown = log_text[:_MAX_LOG_CHARS]

    prompt = (
        f"Log source: {log_source}\n"
        f"Declared log format: {log_format}\n"
        f"Analysis type: {analysis_type}\n\n"
        f"LOG CONTENT (verbatim, read from the workspace"
        f"{'; first %d chars only' % _MAX_LOG_CHARS if truncated else ''}):\n"
        f"-----\n{shown}\n-----\n\n"
        f"Perform a '{analysis_type}' analysis of ONLY the log lines above. "
        "Reference real line numbers where relevant.\n\n"
        'Return a single JSON object with keys "anomalies" (array of '
        '{"line": integer, "description": string}), "patterns" (array of '
        'strings), "root_cause" (string), and "recommendations" (array of '
        "strings)."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise TYPES only — every observation comes from the model's reply
    # about the real log text; empty arrays are honoured as-is.
    anomalies: List[Dict[str, Any]] = [
        _normalise_anomaly(item) for item in as_list(data.get("anomalies"))
    ]
    patterns = [coerce_str(p) for p in as_list(data.get("patterns"))]
    recommendations = [coerce_str(r) for r in as_list(data.get("recommendations"))]
    return {
        "anomalies": anomalies,
        "patterns": patterns,
        "root_cause": coerce_str(data.get("root_cause")),
        "recommendations": recommendations,
    }
