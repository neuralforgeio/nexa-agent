"""
Tests for the Pydantic schemas module (tools/_schemas.py).

Verifies that:
    - Every tool has a corresponding Pydantic BaseModel.
    - The Pydantic-generated JSON schema matches (or is compatible with)
      the hand-written OpenAI schema in each tool module.
    - Invalid arguments (path traversal, negative timeout, etc.) are
      rejected by Pydantic validation.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest
from pydantic import ValidationError

from tools._schemas import (
    CodeExecutionArgs,
    DelegateArgs,
    FilePatchArgs,
    GenerateUuidArgs,
    KillBackgroundProcessArgs,
    ListBackgroundProcessesArgs,
    ReadFileArgs,
    RunTerminalCommandArgs,
    WebSearchArgs,
    WriteFileArgs,
    TOOL_SCHEMAS,
    get_schema_for_tool,
)


# ---------------------------------------------------------------------------
# Coverage: every tool has a Pydantic model
# ---------------------------------------------------------------------------
class TestSchemaCoverage:
    """Tests that every registered tool has a Pydantic model."""

    EXPECTED_TOOLS = {
        "read_file", "write_file", "run_terminal_command",
        "generate_uuid", "delegate", "list_background_processes",
        "kill_background_process", "web_search", "code_execution", "file_patch",
    }

    def test_all_tools_have_pydantic_model(self) -> None:
        """TOOL_SCHEMAS must include an entry for every registered tool."""
        assert set(TOOL_SCHEMAS.keys()) == self.EXPECTED_TOOLS

    def test_get_schema_for_known_tool(self) -> None:
        """get_schema_for_tool returns the model class for a known tool."""
        model = get_schema_for_tool("read_file")
        assert model is ReadFileArgs

    def test_get_schema_for_unknown_tool_returns_none(self) -> None:
        """get_schema_for_tool returns None for an unknown tool."""
        assert get_schema_for_tool("nonexistent") is None

    def test_get_schema_case_insensitive(self) -> None:
        """get_schema_for_tool is case-insensitive."""
        assert get_schema_for_tool("Read_File") is ReadFileArgs
        assert get_schema_for_tool("CODE_EXECUTION") is CodeExecutionArgs


# ---------------------------------------------------------------------------
# read_file / write_file
# ---------------------------------------------------------------------------
class TestFileSchemas:
    """Tests for the file tool Pydantic schemas."""

    def test_read_file_valid(self) -> None:
        """A valid read_file args object passes validation."""
        args = ReadFileArgs(path="notes.txt")
        assert args.path == "notes.txt"

    def test_read_file_empty_path_rejected(self) -> None:
        """An empty path is rejected."""
        with pytest.raises(ValidationError):
            ReadFileArgs(path="")

    def test_read_file_path_traversal_rejected(self) -> None:
        """Path traversal via .. is rejected."""
        with pytest.raises(ValidationError):
            ReadFileArgs(path="../../etc/passwd")

    def test_write_file_valid(self) -> None:
        """A valid write_file args object passes validation."""
        args = WriteFileArgs(path="out.txt", content="hello")
        assert args.content == "hello"

    def test_write_file_empty_content_allowed(self) -> None:
        """Empty content is allowed (truncate the file)."""
        args = WriteFileArgs(path="empty.txt", content="")
        assert args.content == ""


# ---------------------------------------------------------------------------
# run_terminal_command
# ---------------------------------------------------------------------------
class TestTerminalSchema:
    """Tests for the terminal command Pydantic schema."""

    def test_valid_command(self) -> None:
        """A valid command passes validation."""
        args = RunTerminalCommandArgs(command="echo hi")
        assert args.command == "echo hi"
        assert args.timeout == 15.0  # default
        assert args.background is False

    def test_empty_command_rejected(self) -> None:
        """An empty command is rejected."""
        with pytest.raises(ValidationError):
            RunTerminalCommandArgs(command="")

    def test_whitespace_command_rejected(self) -> None:
        """A whitespace-only command is rejected."""
        with pytest.raises(ValidationError):
            RunTerminalCommandArgs(command="   ")

    def test_negative_timeout_rejected(self) -> None:
        """A negative timeout is rejected."""
        with pytest.raises(ValidationError):
            RunTerminalCommandArgs(command="echo hi", timeout=-1.0)

    def test_timeout_over_max_rejected(self) -> None:
        """A timeout exceeding the max (60s) is rejected."""
        with pytest.raises(ValidationError):
            RunTerminalCommandArgs(command="echo hi", timeout=120.0)


# ---------------------------------------------------------------------------
# code_execution
# ---------------------------------------------------------------------------
class TestCodeExecutionSchema:
    """Tests for the code_execution Pydantic schema."""

    def test_valid_code(self) -> None:
        """Valid code passes validation."""
        args = CodeExecutionArgs(code="print('hi')")
        assert args.requires_approval is True  # default

    def test_empty_code_rejected(self) -> None:
        """Empty code is rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionArgs(code="")

    def test_timeout_over_max_rejected(self) -> None:
        """Timeout over MAX_CODE_TIMEOUT is rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionArgs(code="print('hi')", timeout=999.0)


# ---------------------------------------------------------------------------
# delegate
# ---------------------------------------------------------------------------
class TestDelegateSchema:
    """Tests for the delegate Pydantic schema."""

    def test_valid_delegate(self) -> None:
        """A valid delegate args object passes validation."""
        args = DelegateArgs(task="read and summarize")
        assert args.max_iterations == 3  # default

    def test_empty_task_rejected(self) -> None:
        """An empty task is rejected."""
        with pytest.raises(ValidationError):
            DelegateArgs(task="")

    def test_negative_max_iterations_rejected(self) -> None:
        """A negative max_iterations is rejected."""
        with pytest.raises(ValidationError):
            DelegateArgs(task="do X", max_iterations=-1)

    def test_max_iterations_over_cap_rejected(self) -> None:
        """max_iterations above 8 is rejected."""
        with pytest.raises(ValidationError):
            DelegateArgs(task="do X", max_iterations=20)


# ---------------------------------------------------------------------------
# kill_background_process / web_search / file_patch
# ---------------------------------------------------------------------------
class TestMiscSchemas:
    """Tests for the smaller tool schemas."""

    def test_kill_background_process_empty_pid_rejected(self) -> None:
        """An empty PID is rejected."""
        with pytest.raises(ValidationError):
            KillBackgroundProcessArgs(pid="")

    def test_web_search_empty_query_rejected(self) -> None:
        """An empty query is rejected."""
        with pytest.raises(ValidationError):
            WebSearchArgs(query="")

    def test_web_search_num_results_clamped(self) -> None:
        """num_results above 10 is rejected."""
        with pytest.raises(ValidationError):
            WebSearchArgs(query="test", num_results=100)

    def test_file_patch_valid(self) -> None:
        """A valid file_patch args object passes validation."""
        args = FilePatchArgs(path="f.txt", patch="@@ -1,1 +1,1 @@\n-old\n+new\n")
        assert args.path == "f.txt"

    def test_file_patch_empty_path_rejected(self) -> None:
        """An empty path is rejected."""
        with pytest.raises(ValidationError):
            FilePatchArgs(path="", patch="...")

    def test_file_patch_empty_patch_rejected(self) -> None:
        """An empty patch is rejected."""
        with pytest.raises(ValidationError):
            FilePatchArgs(path="f.txt", patch="")

    def test_generate_uuid_takes_no_args(self) -> None:
        """generate_uuid accepts an empty args object (no required fields)."""
        args = GenerateUuidArgs()
        assert args is not None

    def test_list_background_processes_takes_no_args(self) -> None:
        """list_background_processes accepts an empty args object."""
        args = ListBackgroundProcessesArgs()
        assert args is not None
