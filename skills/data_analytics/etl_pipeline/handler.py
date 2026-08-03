# SPDX-License-Identifier: MIT
"""Skill: etl_pipeline.

Purpose: design an ETL pipeline from a source config to a destination config
with transformation steps and an optional schedule. The LLM generates the
pipeline code text, grounded in the REAL source/destination/transformation
configs embedded in the prompt; code falls back to a deterministic skeleton if
the model returns empty text.

Permissions: ``filesystem:workspace:write``, ``terminal:execute``, ``network:*``
(all declared by the manifest; none exercised — no pipeline is deployed).

Honest note: ``pipeline_code`` is generated TEXT, not a deployed or executed
pipeline (documented in the manifest description). ``pipeline_config`` is a
small dict built in code from the input. ``test_results`` is honestly
``{"status": "code_generated_not_executed", "ok": True, ...}`` unless a real
syntax check runs — when the generated code is non-empty Python-looking text a
real ``compile()`` check IS run and its outcome reported truthfully.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from skills._common import (
    as_list,
    ask_llm_json,
    coerce_number,  # noqa: F401  (kept import surface aligned with batch kit)
    coerce_str,
    require,
)
from skills._llm import chat_json  # noqa: F401  (re-exported seam; ask_llm_json uses it)

__all__ = ["handle"]

_SYSTEM = (
    "You are Nexa's ETL pipeline designer. You are given the REAL source "
    "config, destination config, transformation steps, and optional schedule. "
    "Generate Python ETL code that genuinely implements those steps against "
    "the shown configs — do not hallucinate connectors/credentials not "
    "present in the input. Respond with a SINGLE JSON object, and nothing "
    "else (no markdown fences, no prose), with exactly these keys: "
    '"pipeline_code" (a string of Python source implementing extract-'
    "transform-load for the given configs), and "
    '"notes" (a short string describing key design decisions); use an empty '
    "string for notes if not needed. This is generated code text, NOT a "
    "deployed pipeline."
)


def _build_pipeline_config(source, destination, transformations, schedule) -> Dict[str, Any]:
    """Small dict built in code straight from the input."""
    return {
        "source": source,
        "destination": destination,
        "transformations": transformations,
        "schedule": schedule,
    }


def _fallback_code(source, destination, transformations, schedule) -> str:
    """Deterministic skeleton derived from the real configs."""
    lines = [
        '"""Generated ETL pipeline (skeleton, not deployed)."""',
        "",
        f"SOURCE = {json.dumps(source)}",
        f"DESTINATION = {json.dumps(destination)}",
        f"TRANSFORMATIONS = {json.dumps(transformations)}",
        f"SCHEDULE = {json.dumps(schedule)}",
        "",
        "def extract():",
        "    # TODO: read from SOURCE",
        "    raise NotImplementedError('extract not implemented')",
        "",
        "def transform(records):",
        "    # TODO: apply TRANSFORMATIONS",
        "    return records",
        "",
        "def load(records):",
        "    # TODO: write to DESTINATION",
        "    raise NotImplementedError('load not implemented')",
        "",
        "def run():",
        "    load(transform(extract()))",
    ]
    return "\n".join(lines)


def _syntax_check(code: str) -> Dict[str, Any]:
    """Run a real compile() check; report truthfully. Never pretends to run."""
    result: Dict[str, Any] = {
        "status": "code_generated_not_executed",
        "ok": True,
        "checks": [],
    }
    text = code.strip()
    # Only attempt a syntax check if it looks like Python source.
    looks_python = any(
        tok in text for tok in ("def ", "import ", "class ", "=", "print(", "raise ")
    )
    if looks_python and text:
        try:
            compile(text, "<etl_pipeline>", "exec")
            result["checks"].append({"name": "python_syntax_compile", "ok": True})
        except SyntaxError as exc:
            result["checks"].append(
                {"name": "python_syntax_compile", "ok": False, "error": str(exc)}
            )
            result["ok"] = False
    return result


async def handle(input_data: dict, provider) -> dict:
    """Generate ETL pipeline code text + config; code is NOT deployed."""
    source = require(input_data, "source", dict, "the source config")
    destination = require(input_data, "destination", dict, "the destination config")
    transformations = require(input_data, "transformations", list, "the transformation steps")
    schedule = coerce_str(input_data.get("schedule"), default="") or None

    prompt = (
        f"Source config (REAL): {json.dumps(source, indent=2)}\n"
        f"Destination config (REAL): {json.dumps(destination, indent=2)}\n"
        f"Transformations (REAL): {json.dumps(transformations, indent=2)}\n"
        f"Schedule: {schedule or '(none)'}\n\n"
        "Generate Python ETL code that implements extract/transform/load for "
        "EXACTLY these configs and steps. Return a single JSON object with "
        '"pipeline_code" (string of Python source) and "notes" (string).'
    )

    payload = await ask_llm_json(provider, prompt, system=_SYSTEM, fallback=None)

    pipeline_code = coerce_str(payload.get("pipeline_code"))
    if not pipeline_code.strip():
        pipeline_code = _fallback_code(source, destination, transformations, schedule)

    pipeline_config = _build_pipeline_config(source, destination, transformations, schedule)
    test_results = _syntax_check(pipeline_code)
    notes = coerce_str(payload.get("notes"))
    if notes:
        test_results["notes"] = notes

    return {
        "pipeline_code": pipeline_code,
        "pipeline_config": pipeline_config,
        "test_results": test_results,
    }
