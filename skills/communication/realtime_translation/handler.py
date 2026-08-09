"""
OpenForge — realtime_translation skill (communication)
=======================================================

Purpose
-------
Translate a live audio stream from ``source_lang`` to ``target_lang`` in
near real time, per the manifest: ``translated_stream`` (str — a reference
to the translated audio stream) and ``latency`` (number, seconds,
end-to-end).

Permissions
-----------
Declared: ``network:*`` (a real deployment streams audio to/from a
translation service). THIS handler opens no socket and makes no network
call — see the honesty note.

Honesty note
------------
Real bidirectional *streaming* translation requires infrastructure that is
NOT present in this runtime: a streaming ASR stage, a streaming MT stage, a
streaming TTS stage, and the media pipeline binding them together. None of
that exists here, and this handler refuses to fake it:

  * ``translated_stream`` is ``""`` — no translated stream was produced or
    claimed;
  * ``latency`` is ``0.0`` — no translation pipeline ran, so there is no
    real end-to-end latency to report.

The result is schema-valid by construction, the handler never raises on the
missing infrastructure, and it never fabricates either a stream reference or
a latency figure. Standing up the streaming ASR/MT/TTS pipeline is the
documented path to real availability.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from skills._common import (  # noqa: F401  (contract imports kept aligned with batch kit)
    as_list,
    ask_llm_json,
    coerce_number,
    coerce_str,
    require,
)

__all__ = ["handle"]


async def handle(input_data: dict, provider) -> dict:
    """
    Accept the realtime-translation request and — with no streaming
    translation infrastructure present — return the honest, schema-valid
    "not available" payload.

    Raises:
        SkillInputError: Missing/wrongly-typed ``audio_stream``,
            ``source_lang``, or ``target_lang``.
    """
    require(input_data, "audio_stream", str, "audio stream reference")
    require(input_data, "source_lang", str, "source language")
    require(input_data, "target_lang", str, "target language")

    # Honest degradation: streaming bidirectional translation needs ASR + MT
    # + TTS infrastructure that is not present, so no translated stream is
    # produced ("") and no real latency was measured (0.0).
    return {
        "translated_stream": "",
        "latency": 0.0,
    }
