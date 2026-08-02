"""
Tests for the Trajectory Recorder (v3.1.0).

Verifies:
    - TurnTrajectory serializes to a single JSONL line.
    - TrajectoryRecorder appends to ~/.nexa/logs/trajectory.jsonl.
    - read_all() round-trips.
    - count() returns the line count.
    - clear() deletes the file.
    - System prompt is truncated to SYSTEM_PROMPT_TRUNCATE.
    - is_trajectory_enabled reads NEXA_TRAJECTORY env.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import json
import os
from pathlib import Path

import pytest

from agent.observability.trajectory_recorder import (
    DEFAULT_TRAJECTORY_PATH,
    SYSTEM_PROMPT_TRUNCATE,
    TrajectoryRecorder,
    TurnTrajectory,
    is_trajectory_enabled,
)


class TestTurnTrajectory:
    """Tests for the TurnTrajectory dataclass."""

    def test_to_jsonl_single_line(self) -> None:
        """to_jsonl() returns a single line (no newlines inside)."""
        t = TurnTrajectory(
            session_id="conv-1",
            turn_id=1,
            user_message="hi",
            assistant_response="hello!",
        )
        line = t.to_jsonl()
        assert "\n" not in line
        d = json.loads(line)
        assert d["session_id"] == "conv-1"
        assert d["user_message"] == "hi"
        assert d["assistant_response"] == "hello!"

    def test_to_dict_returns_full(self) -> None:
        """to_dict() returns the full system prompt (no truncation)."""
        long_prompt = "x" * (SYSTEM_PROMPT_TRUNCATE + 100)
        t = TurnTrajectory(
            session_id="conv-1", turn_id=1, user_message="hi",
            system_prompt=long_prompt,
        )
        d = t.to_dict()
        assert len(d["system_prompt"]) == SYSTEM_PROMPT_TRUNCATE + 100

    def test_system_prompt_truncated_in_jsonl(self) -> None:
        """The system prompt is truncated in JSONL output."""
        long_prompt = "x" * (SYSTEM_PROMPT_TRUNCATE + 100)
        t = TurnTrajectory(
            session_id="conv-1", turn_id=1, user_message="hi",
            system_prompt=long_prompt,
        )
        line = t.to_jsonl()
        d = json.loads(line)
        assert len(d["system_prompt"]) <= SYSTEM_PROMPT_TRUNCATE + 20  # +truncation marker
        assert "truncated" in d["system_prompt"]

    def test_timestamp_auto_generated(self) -> None:
        """A timestamp is auto-generated if not provided."""
        t = TurnTrajectory(session_id="c", turn_id=1, user_message="x")
        assert t.timestamp  # non-empty
        # ISO 8601 format.
        assert "T" in t.timestamp


class TestTrajectoryRecorder:
    """Tests for the TrajectoryRecorder class."""

    def test_record_appends_to_file(self, tmp_path: Path) -> None:
        """record() appends a line to the JSONL file."""
        path = tmp_path / "traj.jsonl"
        rec = TrajectoryRecorder(path=path)
        rec.record(TurnTrajectory(
            session_id="conv-1", turn_id=1, user_message="hi",
            assistant_response="hello!",
        ))
        assert path.exists()
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        d = json.loads(lines[0])
        assert d["session_id"] == "conv-1"

    def test_record_multiple_lines(self, tmp_path: Path) -> None:
        """Multiple records produce multiple lines."""
        path = tmp_path / "traj.jsonl"
        rec = TrajectoryRecorder(path=path)
        for i in range(5):
            rec.record(TurnTrajectory(
                session_id="conv-1", turn_id=i, user_message=f"msg-{i}",
            ))
        assert rec.count() == 5

    def test_read_all_roundtrips(self, tmp_path: Path) -> None:
        """read_all() returns the recorded trajectories."""
        path = tmp_path / "traj.jsonl"
        rec = TrajectoryRecorder(path=path)
        rec.record(TurnTrajectory(
            session_id="conv-1", turn_id=1, user_message="hi",
            assistant_response="hello!",
        ))
        rec.record(TurnTrajectory(
            session_id="conv-1", turn_id=2, user_message="bye",
            assistant_response="goodbye!",
        ))
        all_trajs = rec.read_all()
        assert len(all_trajs) == 2
        assert all_trajs[0].user_message == "hi"
        assert all_trajs[1].user_message == "bye"

    def test_read_all_empty_when_file_missing(self, tmp_path: Path) -> None:
        """read_all() returns [] when the file doesn't exist."""
        rec = TrajectoryRecorder(path=tmp_path / "nonexistent.jsonl")
        assert rec.read_all() == []

    def test_count_zero_when_missing(self, tmp_path: Path) -> None:
        """count() returns 0 when the file doesn't exist."""
        rec = TrajectoryRecorder(path=tmp_path / "nonexistent.jsonl")
        assert rec.count() == 0

    def test_clear_deletes_file(self, tmp_path: Path) -> None:
        """clear() deletes the file and returns the line count."""
        path = tmp_path / "traj.jsonl"
        rec = TrajectoryRecorder(path=path)
        rec.record(TurnTrajectory(session_id="c", turn_id=1, user_message="x"))
        rec.record(TurnTrajectory(session_id="c", turn_id=2, user_message="y"))
        n = rec.clear()
        assert n == 2
        assert not path.exists()

    def test_clear_zero_when_missing(self, tmp_path: Path) -> None:
        """clear() returns 0 when the file doesn't exist."""
        rec = TrajectoryRecorder(path=tmp_path / "nonexistent.jsonl")
        assert rec.clear() == 0

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        """Malformed JSON lines are skipped by read_all()."""
        path = tmp_path / "traj.jsonl"
        path.write_text(
            '{"session_id":"c","turn_id":1,"user_message":"hi"}\n'
            'this is not json\n'
            '{"session_id":"c","turn_id":2,"user_message":"bye"}\n',
            encoding="utf-8",
        )
        rec = TrajectoryRecorder(path=path)
        all_trajs = rec.read_all()
        assert len(all_trajs) == 2  # malformed line skipped


class TestIsTrajectoryEnabled:
    """Tests for the env-var check."""

    def test_default_off(self, monkeypatch) -> None:
        """Trajectory recording is off by default."""
        monkeypatch.delenv("NEXA_TRAJECTORY", raising=False)
        assert is_trajectory_enabled() is False

    def test_enabled_when_set(self, monkeypatch) -> None:
        """NEXA_TRAJECTORY=1 enables it."""
        monkeypatch.setenv("NEXA_TRAJECTORY", "1")
        assert is_trajectory_enabled() is True

    def test_enabled_when_true(self, monkeypatch) -> None:
        """NEXA_TRAJECTORY=true enables it."""
        monkeypatch.setenv("NEXA_TRAJECTORY", "true")
        assert is_trajectory_enabled() is True
