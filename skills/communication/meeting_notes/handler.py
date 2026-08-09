"""
OpenForge — meeting_notes skill (communication)
================================================

Purpose
-------
Turn a meeting recording into structured notes: ``transcript`` (str),
``action_items`` (array of ``{task, assignee?, due_date?}``), ``decisions``
(list of str), and ``summary`` (str) — the manifest contract.

Permissions
-----------
Declared: ``filesystem:workspace`` (the audio file referenced by
``audio_path`` is resolved and sized through
:func:`agent.tool_api.workspace_path`, sandboxed to ``FORGE_WORKSPACE``) and
``memory:write`` (declared by the manifest; this handler itself does not
write memory).

Honesty note
------------
This environment ships NO ASR backend (no whisper, no speech model), so this
handler genuinely CANNOT transcribe the raw audio bytes itself — and it
never pretends to. What it honestly DOES:

  * verifies the referenced file really exists in the workspace and reads
    its real byte length (via ``tool_api.workspace_path``);
  * hands the model the caller-provided ``meeting_context``/``attendees``
    plus the real file metadata, and asks for a structured notes skeleton —
    derived ONLY from context the caller actually supplied.

Because raw-audio transcription is unavailable, the model is explicitly
instructed to leave ``transcript`` EMPTY when it has no genuine transcript
text — a small local model cannot hear an ``.mp3``. ``transcript`` therefore
comes from the model's reply verbatim and may be empty; ``action_items``,
``decisions``, and ``summary`` likewise come from the model over the provided
context, and fall back to schema-valid empty fields (never fabricated) when
the model supplies nothing usable. LLM/parse errors propagate — no
swallowing, no fabrication, no fake "transcription" claims.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle", "SYSTEM"]

SYSTEM = (
    "You are the meeting_notes skill inside the Nexa Agent skills system. "
    "CRITICAL CONSTRAINT: you are a text model — you CANNOT hear audio and "
    "no ASR transcript of the referenced recording is available to you. All "
    "you genuinely have is the caller-provided meeting context and attendee "
    "list. Never pretend to have heard the recording and never invent "
    "quotes, decisions, or action items that are not grounded in the "
    "provided context. Respond with a single JSON object and nothing else — "
    "no prose, no markdown fence. The object MUST have these keys:\n"
    '  "transcript": string — MUST be "" (empty) because no ASR transcript '
    "exists; never fabricate one;\n"
    '  "action_items": array of objects with "task" (string) and optional '
    '"assignee" (string) and "due_date" (string) — a structured skeleton '
    "derived ONLY from the provided meeting context; use an empty array if "
    "the context supports none;\n"
    '  "decisions": array of strings — decisions explicitly present in the '
    "provided context; use an empty array if none are;\n"
    '  "summary": string — a short honest note describing the meeting based '
    "on the provided context, clearly framed as context-derived (not a "
    "transcript)."
)


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


def _build_prompt(
    audio_path: str,
    size_bytes: int,
    meeting_context: str,
    attendees: List[str],
) -> str:
    attendee_line = ", ".join(attendees) if attendees else "(none provided)"
    context_block = meeting_context or "(none provided)"
    return (
        f"Audio file (verified to exist in the workspace): {audio_path} "
        f"({size_bytes} bytes)\n"
        f"Attendees (caller-provided): {attendee_line}\n\n"
        "Meeting context (caller-provided — this is ALL the real information "
        "available; there is NO audio transcript):\n"
        f"-----\n{context_block}\n-----\n\n"
        "Produce a structured meeting-notes skeleton grounded ONLY in the "
        "context above. Remember: transcript MUST be an empty string because "
        "no ASR backend exists here and you cannot hear the recording.\n\n"
        'Return a single JSON object with keys "transcript" (string), '
        '"action_items" (array of objects with "task" [string], optional '
        '"assignee" [string] and "due_date" [string]), "decisions" (array of '
        'strings), and "summary" (string).'
    )


def _normalise_action_item(item: Any) -> Dict[str, Any]:
    """Map a raw model action item to the manifest's per-item schema."""
    if isinstance(item, dict):
        out: Dict[str, Any] = {"task": coerce_str(item.get("task"))}
        assignee = coerce_str(item.get("assignee"))
        due_date = coerce_str(item.get("due_date"))
        if assignee:
            out["assignee"] = assignee
        if due_date:
            out["due_date"] = due_date
        return out
    # Non-object item (e.g. a bare string): keep the content as the task.
    return {"task": coerce_str(item)}


async def handle(input_data: dict, provider) -> dict:
    """
    Produce structured meeting notes from context + a verified audio file.

    Raises:
        SkillInputError: Missing/wrongly-typed ``audio_path``, or the file
            does not exist in the workspace.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.

    Without an ASR backend this handler cannot transcribe the recording;
    the returned ``transcript`` is whatever the (audio-deaf) model honestly
    reports — normally empty — and never a fabricated transcription.
    """
    audio_path = require(input_data, "audio_path", str, "path to the recording")
    size_bytes = _resolve_audio(audio_path)

    meeting_context = coerce_str(input_data.get("meeting_context"))
    attendees = [
        coerce_str(a) for a in as_list(input_data.get("attendees")) if coerce_str(a).strip()
    ]

    prompt = _build_prompt(audio_path, size_bytes, meeting_context, attendees)
    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise TYPES only — content always comes from the model's reply over
    # the real context. Empty fallbacks keep the output schema-valid without
    # fabricating a transcript that a text-only model could not produce.
    action_items = [
        _normalise_action_item(item)
        for item in as_list(data.get("action_items"))
        if _normalise_action_item(item)["task"]
    ]
    decisions = [
        coerce_str(d) for d in as_list(data.get("decisions")) if coerce_str(d).strip()
    ]

    return {
        "transcript": coerce_str(data.get("transcript")),
        "action_items": action_items,
        "decisions": decisions,
        "summary": coerce_str(data.get("summary")),
    }
