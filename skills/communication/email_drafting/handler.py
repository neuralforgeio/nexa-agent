"""
OpenForge — email_drafting skill (communication)
=================================================

Purpose
-------
Draft an email from real caller-supplied ``bullet_points`` in a chosen
``tone`` (``formal`` | ``casual`` | ``persuasive`` | ``apologetic``) for a
named ``recipient``. Returns the manifest contract: ``email_subject`` (str),
``email_body`` (str), and ``alternatives`` (list of str — alternative
subject-line phrasings).

Permissions
-----------
Declared: ``memory:read``. This handler itself touches neither the
filesystem nor memory — drafting is a pure LLM transformation of the caller's
input.

Honesty note
------------
Everything in the output is produced by the model from a prompt that embeds
the REAL bullet points, tone, recipient, and signature preference — nothing
is template-generated or pre-canned. If the model reply is not parseable
JSON, ``ValueError`` propagates rather than fabricating an email; if the
provider signals an error, ``RuntimeError`` propagates. Only TYPES are
normalised (string coercion, list wrapping) so the executor's output
validation always sees schema-typed values.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from skills._common import as_list, ask_llm_json, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle", "SYSTEM"]

_TONES = ("formal", "casual", "persuasive", "apologetic")

SYSTEM = (
    "You are the email_drafting skill inside the OpenForge skills system. "
    "You are given REAL bullet points, a tone, a recipient, and whether a "
    "signature block is wanted. Draft an email that covers ONLY what the "
    "bullet points actually say — never invent facts, names, dates, or "
    "commitments that are not in the bullets. Respond with a single JSON "
    "object and nothing else — no prose, no markdown fence. The object MUST "
    "have these keys:\n"
    '  "email_subject": string — a concise subject line reflecting the bullets;\n'
    '  "email_body": string — the full email body in the requested tone, '
    "addressed to the recipient, including a signature block when requested;\n"
    '  "alternatives": array of strings — 2-3 alternative subject-line '
    "phrasings (may be an empty array)."
)


def _build_prompt(
    bullet_points: List[str],
    tone: str,
    recipient: str,
    include_signature: bool,
) -> str:
    bullets = "\n".join(f"- {b}" for b in bullet_points)
    return (
        f"Recipient: {recipient}\n"
        f"Tone: {tone}\n"
        f"Include signature: {'yes' if include_signature else 'no'}\n\n"
        f"Bullet points to cover (the REAL content of the email):\n"
        f"{bullets}\n\n"
        "Write the email now. Cover every bullet above, add nothing that is "
        "not grounded in them, and match the requested tone exactly. "
        'Return a single JSON object with keys "email_subject" (string), '
        '"email_body" (string), and "alternatives" (array of strings).'
    )


async def handle(input_data: dict, provider) -> dict:
    """
    Draft an email from the caller's bullet points via the model.

    Raises:
        SkillInputError: Missing/wrongly-typed ``bullet_points``, ``tone``,
            or ``recipient``.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.
    """
    bullet_points = require(input_data, "bullet_points", list, "bullet points")
    tone = require(input_data, "tone", str, "tone")
    recipient = require(input_data, "recipient", str, "recipient")
    include_signature = input_data.get("include_signature", False)
    if not isinstance(include_signature, bool):
        raise SkillInputError(
            f"field 'include_signature' must be bool, got {type(include_signature).__name__}"
        )

    bullets = [coerce_str(b) for b in bullet_points if coerce_str(b).strip()]
    if not bullets:
        raise SkillInputError(
            "bullet_points must contain at least one non-empty string"
        )

    prompt = _build_prompt(bullets, tone, recipient, include_signature)
    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise TYPES only — the words (subject, body, alternative phrasings)
    # always come from the model's reply about the real bullets.
    alternatives = [coerce_str(a) for a in as_list(data.get("alternatives"))]
    alternatives = [a for a in alternatives if a]

    return {
        "email_subject": coerce_str(data.get("email_subject")),
        "email_body": coerce_str(data.get("email_body")),
        "alternatives": alternatives,
    }
