"""
Nexa Agent — Trajectory Export (v3.1.0)
========================================

Records the full prompt → tool → response trajectory of every conversation
turn as JSONL (one JSON object per line). The resulting file is suitable for
fine-tuning datasets (e.g. LoRA/QLoRA on a small local model).

Each line is a JSON object with:
    - ``session_id``:  The conversation ID.
    - ``turn_id``:     Monotonic turn index within the session.
    - ``user_message``: The user's input.
    - ``system_prompt``: The full system prompt (truncated to 2KB).
    - ``tool_calls``:  List of {name, arguments, ok, output, duration_ms}.
    - ``assistant_response``: The final answer.
    - ``errors``:       List of error strings encountered.
    - ``confidence``:  Confidence score (0.0–1.0).
    - ``timestamp``:    ISO 8601 timestamp.

The trajectory is appended to ``~/.nexa/logs/trajectory.jsonl`` (one file,
append-only, so it survives restarts and grows incrementally).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from nexa.config import NEXA_HOME


#: Default trajectory file path.
DEFAULT_TRAJECTORY_PATH: Path = NEXA_HOME / "logs" / "trajectory.jsonl"

#: Truncate the system prompt in the trajectory to keep file size manageable.
SYSTEM_PROMPT_TRUNCATE: int = 2048


@dataclass
class TurnTrajectory:
    """
    The trajectory of a single conversation turn.

    Attributes:
        session_id:          The conversation ID.
        turn_id:             Monotonic turn index.
        user_message:        The user's input.
        system_prompt:       The full system prompt (truncated).
        tool_calls:          List of tool-call records.
        assistant_response: The final answer.
        errors:              Errors encountered during the turn.
        confidence:          Confidence score (0.0–1.0).
        timestamp:           ISO 8601 timestamp.
    """

    session_id: str
    turn_id: int
    user_message: str
    system_prompt: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    assistant_response: str = ""
    errors: List[str] = field(default_factory=list)
    confidence: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_jsonl(self) -> str:
        """
        Serialize to a single JSONL line (no trailing newline).

        Returns:
            A JSON string (one line, no indentation).
        """
        d = asdict(self)
        # Truncate the system prompt to keep file size manageable.
        if len(d["system_prompt"]) > SYSTEM_PROMPT_TRUNCATE:
            d["system_prompt"] = d["system_prompt"][:SYSTEM_PROMPT_TRUNCATE] + "…[truncated]"
        return json.dumps(d, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (with full system prompt)."""
        return asdict(self)


class TrajectoryRecorder:
    """
    Append-only trajectory recorder.

    Writes one JSONL line per turn to ``~/.nexa/logs/trajectory.jsonl``.
    Failures are silently swallowed (trajectory is best-effort — must never
    break the agent loop).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """
        Initialize the recorder.

        Args:
            path: Override for the trajectory file (default NEXA_HOME/logs/trajectory.jsonl).
        """
        self.path: Path = path or DEFAULT_TRAJECTORY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, trajectory: TurnTrajectory) -> None:
        """
        Append a turn trajectory to the JSONL file.

        Args:
            trajectory: The :class:`TurnTrajectory` to record.

        Example:
            >>> rec = TrajectoryRecorder()
            >>> rec.record(TurnTrajectory(  # doctest: +SKIP
            ...     session_id="conv-123", turn_id=1, user_message="hi",
            ...     assistant_response="hello!",
            ... ))
        """
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(trajectory.to_jsonl() + "\n")
        except OSError:
            # Best-effort — never break the agent loop.
            pass

    def read_all(self) -> List[TurnTrajectory]:
        """
        Read all recorded trajectories from the JSONL file.

        Returns:
            A list of :class:`TurnTrajectory` objects.
        """
        if not self.path.exists():
            return []
        out: List[TurnTrajectory] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                out.append(TurnTrajectory(**d))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    def count(self) -> int:
        """Return the number of recorded trajectories."""
        if not self.path.exists():
            return 0
        n = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                n += 1
        return n

    def clear(self) -> int:
        """
        Delete the trajectory file.

        Returns:
            The number of lines deleted (0 if file didn't exist).
        """
        if not self.path.exists():
            return 0
        n = self.count()
        try:
            self.path.unlink()
        except OSError:
            pass
        return n


def is_trajectory_enabled() -> bool:
    """Return True if trajectory recording is enabled via env (NEXA_TRAJECTORY=1)."""
    return os.environ.get("NEXA_TRAJECTORY", "0").lower() in ("1", "true", "yes")
