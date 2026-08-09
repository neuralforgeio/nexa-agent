"""
Skill: incident_response
========================

Triage an incident from its REAL description, severity (``P0``-``P3``), and
affected services. Returns a triage assessment, proposed runbook steps (each
flagged with whether it is safe to auto-execute), and an escalation plan.

Permissions used:
  * ``filesystem:workspace`` / ``terminal:execute`` / ``network:*`` —
    declared by the manifest; this handler executes NO runbook commands and
    makes NO network calls. Nothing here pages anyone, restarts anything, or
    mitigates the incident.
  * ``memory:read`` — declared by the manifest; this handler itself does not
    touch memory.

Honesty note: the triage assessment and runbook steps come from the model's
reply about the caller's real incident text — but ``escalation`` is always a
fixed, plainly-labelled placeholder (``state: "suggest_only"`` with example
contacts) because this runtime has no paging/IM integrations. The skill NEVER
claims an incident was resolved or even acted on: every runbook step is a
*suggestion*, and only steps the model itself flags ``safe_to_auto_execute``
are marked as such for a human to approve. If the model's reply is not
parseable JSON, ``ValueError`` propagates rather than fabricating a runbook.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from skills._common import ask_llm_json, as_list, coerce_number, coerce_str  # noqa: F401
from skills._common import require
from skills.registry import SkillInputError

__all__ = ["handle"]

_SEVERITIES = ("P0", "P1", "P2", "P3")

SYSTEM = (
    "You are Forge's incident-response advisor. You are given the REAL "
    "incident description supplied by an on-call operator, the declared "
    "severity (P0 | P1 | P2 | P3), and the REAL list of affected services. "
    "Base every assessment ONLY on the information given — never invent "
    "metrics, deploys, log lines, or root causes you were not told about. "
    "Respond with a SINGLE JSON object, and nothing else (no markdown "
    "fences, no prose around it), with exactly these keys:\n"
    '  "triage": an object with keys "summary" (string — assessment of what '
    'is happening), "urgency" (string, e.g. "immediate" | "high" | '
    '"normal"), "impact" (string), and "owner" (string — the ROLE that '
    'should own this, e.g. "on-call-sre", not a fabricated person).\n'
    '  "runbook_steps": an array of objects, each with keys "step" (integer, '
    '1-based ordering), "command" (string — the concrete command or action; '
    '"" for purely investigative steps), and "safe_to_auto_execute" '
    "(boolean — true ONLY for read-only/diagnostic steps such as checking "
    "status or logs; false for anything that mutates state). Steps are "
    "SUGGESTIONS for a human to approve — phrase them as such.\n"
    "Do not include an escalation key — escalation is handled by the caller."
)

# Escalation is never actually performed by this runtime (no paging/IM
# integrations), so it is a fixed, clearly-labelled placeholder rather than
# anything that claims contacts were notified.
_ESCALATION_STUB = {"state": "suggest_only", "contacts": ["team-lead@example.com"]}

_URGENCY_BY_SEVERITY = {"P0": "immediate", "P1": "high", "P2": "normal", "P3": "low"}
_OWNER_BY_SEVERITY = {"P0": "incident-commander", "P1": "on-call-sre",
                      "P2": "service-owner", "P3": "service-owner"}


def _coerce_step_number(value: Any, fallback: int) -> int:
    """Best-effort positive int for a runbook step number; never raises."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value if value > 0 else fallback
    if isinstance(value, float):
        return int(value) if value > 0 else fallback
    if isinstance(value, str):
        try:
            n = int(float(value.strip()))
            return n if n > 0 else fallback
        except ValueError:
            return fallback
    return fallback


def _normalise_step(item: Any, position: int) -> Dict[str, Any]:
    """Map a raw model step to {step:int, command:str, safe_to_auto_execute:bool}.

    ``safe_to_auto_execute`` defaults to False unless the model explicitly
    flags the step true — the skill never executes anything either way, and a
    wrong ``true`` default would be a dangerous lie.
    """
    if isinstance(item, dict):
        return {
            "step": _coerce_step_number(item.get("step"), position),
            "command": coerce_str(item.get("command")),
            "safe_to_auto_execute": item.get("safe_to_auto_execute") is True,
        }
    return {"step": position, "command": coerce_str(item), "safe_to_auto_execute": False}


async def handle(input_data: dict, provider) -> dict:
    """Triage the incident and return assessment + suggested runbook."""
    description = require(
        input_data, "incident_description", str, "incident description"
    )
    severity = require(input_data, "severity", str, "severity")
    affected = require(input_data, "affected_services", list, "affected services")
    if severity not in _SEVERITIES:
        raise SkillInputError(
            f"severity must be one of {sorted(_SEVERITIES)}, got {severity!r}"
        )
    if not affected or not all(isinstance(s, str) for s in affected):
        raise SkillInputError("affected_services must be a non-empty list of strings")

    prompt = (
        f"Declared severity: {severity}\n"
        f"Affected services (real, supplied by the caller): {json.dumps(affected)}\n\n"
        f"INCIDENT DESCRIPTION (verbatim, supplied by the caller):\n"
        f"-----\n{description}\n-----\n\n"
        "Triage this incident and propose a runbook of suggested steps for a "
        "human operator to approve.\n\n"
        'Return a single JSON object with keys "triage" ({"summary": string, '
        '"urgency": string, "impact": string, "owner": string}) and '
        '"runbook_steps" (array of {"step": integer, "command": string, '
        '"safe_to_auto_execute": boolean}).'
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Triage: model's grounded assessment, with severity-consistent defaults
    # for fields the model omitted, and the caller's REAL severity pinned in.
    raw_triage = data.get("triage")
    triage: Dict[str, Any] = dict(raw_triage) if isinstance(raw_triage, dict) else {}
    triage["summary"] = coerce_str(triage.get("summary"))
    triage["urgency"] = (
        coerce_str(triage.get("urgency")) or _URGENCY_BY_SEVERITY[severity]
    )
    triage["impact"] = coerce_str(triage.get("impact"))
    triage["owner"] = coerce_str(triage.get("owner")) or _OWNER_BY_SEVERITY[severity]
    triage["severity"] = severity
    triage["affected_services"] = list(affected)

    runbook_steps: List[Dict[str, Any]] = [
        _normalise_step(item, position=i + 1)
        for i, item in enumerate(as_list(data.get("runbook_steps")))
    ]

    return {
        "triage": triage,
        "runbook_steps": runbook_steps,
        # Honest placeholder: nothing was escalated, paged, or notified.
        "escalation": dict(_ESCALATION_STUB),
    }
