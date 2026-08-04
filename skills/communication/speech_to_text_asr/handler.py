"""
Nexa Agent — speech_to_text_asr skill (communication)
=====================================================

Purpose
-------
Transcribe an audio file to text with an optional language hint and
optional speaker diarization, per the manifest: ``transcript`` (str),
``segments`` (array of ``{start, end, text, speaker?}``), ``language`` (str).

Permissions
-----------
Declared: ``filesystem:workspace`` (the audio file referenced by
``audio_path`` is resolved and inspected through
:func:`agent.tool_api.workspace_path`, sandboxed to ``NEXA_WORKSPACE``) and
``network:*`` (ASR backends normally live behind a service; declared by the
manifest — no network call is made in this build).

Honesty note
------------
**There is NO ASR backend bundled with this runtime** (no whisper, no
Vosk, no remote speech service is configured here). Real automatic speech
recognition requires one of those external backends, and this handler
gracefully degrades instead of pretending:

  * it verifies the referenced audio file genuinely exists in the workspace
    (raising :class:`skills.registry.SkillInputError` if the path is invalid
    or the file is missing);
  * it then returns the HONEST "no backend available" result — an empty
    ``transcript``, empty ``segments``, and the caller's ``language`` hint
    (or ``"unknown"``) — all schema-valid by construction.

It MUST NOT raise just because no speech backend exists, and it NEVER
fabricates a transcript or timing segments for audio it cannot decode.
Configuring a real ASR backend (e.g. whisper) is the documented path to
real transcription; this handler is the honest placeholder until then.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent import tool_api
from skills._common import (  # noqa: F401  (contract imports kept aligned with batch kit)
    as_list,
    ask_llm_json,
    coerce_number,
    coerce_str,
    require,
)
from skills.registry import SkillInputError

__all__ = ["handle"]


def _resolve_audio(audio_path: str) -> int:
    """
    Resolve ``audio_path`` inside the workspace and return its byte length.

    Raises:
        SkillInputError: Path escapes the workspace, or the file is missing.
    """
    try:
        p = tool_api.workspace_path(audio_path)
    except ValueError as exc:
        raise SkillInputError(f"invalid audio_path {audio_path!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"file {audio_path!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )
    return p.stat().st_size


async def handle(input_data: dict, provider) -> dict:
    """
    Verify the audio file exists, then gracefully degrade to an honest
    no-backend result.

    With no ASR backend present there is no genuine transcript to return
    (the model is never asked to hallucinate one from audio bytes it cannot
    hear), so the output is schema-valid and honestly empty.

    Raises:
        SkillInputError: Missing/wrongly-typed ``audio_path``, or the file
            does not exist in the workspace.
    """
    audio_path = require(input_data, "audio_path", str, "path to the audio file")
    _resolve_audio(audio_path)  # existence check only; bytes are not decoded here

    language = coerce_str(input_data.get("language")) or "unknown"
    # ``diarize`` is accepted (and validated by the registry's input_schema
    # when run through execute_skill) but cannot be honoured without a
    # diarization-capable ASR backend — the honest result has no segments.
    diarize = input_data.get("diarize", False)
    if not isinstance(diarize, bool):
        raise SkillInputError(
            f"field 'diarize' must be bool, got {type(diarize).__name__}"
        )

    return {
        "transcript": "",
        "segments": [],
        "language": language,
    }
