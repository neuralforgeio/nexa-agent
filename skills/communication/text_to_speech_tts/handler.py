"""
Nexa Agent — text_to_speech_tts skill (communication)
=====================================================

Purpose
-------
Synthesize speech from ``text`` with a chosen ``voice``
(``male`` | ``female`` | ``neutral``), ``speed`` (number, default 1.0), and
``language``, per the manifest: ``audio_path`` (str), ``duration`` (number,
seconds), and ``metadata`` (object).

Permissions
-----------
Declared: ``filesystem:workspace:write`` (a real TTS build would write the
audio artifact into the workspace) and ``network:*`` (TTS engines often live
behind a service). THIS handler writes nothing and makes no network call —
see the honesty note.

Honesty note
------------
**There is NO TTS backend bundled with this runtime** (no Piper, no
Coqui, no cloud speech service is configured here). Rather than fabricating
an artifact, this handler gracefully degrades and returns the HONEST
"nothing was synthesized" result:

  * ``audio_path`` is ``""`` — no audio file was created (this handler does
    NOT write a file it cannot genuinely synthesize, and never claims to);
  * ``duration`` is ``0.0`` — there is no audio to measure;
  * ``metadata`` states exactly what happened:
    ``{"synthesized": False, "reason": "no TTS backend configured",
    "voice": ..., "speed": ..., "language": ...}``.

The result is schema-valid by construction and the handler never raises on
the missing backend — graceful degradation, not failure. Configuring a real
TTS engine is the documented path to real synthesis.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict

from agent import tool_api  # noqa: F401  (workspace write seam for a real backend)
from skills._common import (  # noqa: F401  (contract imports kept aligned with batch kit)
    as_list,
    ask_llm_json,
    coerce_number,
    coerce_str,
    require,
)
from skills.registry import SkillInputError

__all__ = ["handle"]

_VOICES = ("male", "female", "neutral")


async def handle(input_data: dict, provider) -> dict:
    """
    Accept the TTS request and — with no backend configured — return the
    honest, schema-valid "not synthesized" payload.

    Raises:
        SkillInputError: Missing/wrongly-typed ``text``, ``voice``, or
            ``language``; an out-of-enum ``voice``; or a non-numeric
            ``speed``.
    """
    text = require(input_data, "text", str, "text to synthesize")
    voice = require(input_data, "voice", str, "voice")
    language = require(input_data, "language", str, "language")

    if voice not in _VOICES:
        raise SkillInputError(
            f"voice must be one of {sorted(_VOICES)}, got {voice!r}"
        )

    speed_raw = input_data.get("speed", 1.0)
    if isinstance(speed_raw, bool) or not isinstance(speed_raw, (int, float)):
        raise SkillInputError(
            f"field 'speed' must be a number, got {type(speed_raw).__name__}"
        )
    speed = float(speed_raw)

    # Honest degradation: no TTS backend exists in this runtime, so nothing
    # is synthesized and no audio artifact is written or claimed.
    metadata: Dict[str, Any] = {
        "synthesized": False,
        "reason": "no TTS backend configured",
        "voice": voice,
        "speed": speed,
        "language": language,
        "text_length": len(text),
    }
    return {
        "audio_path": "",
        "duration": 0.0,
        "metadata": metadata,
    }
