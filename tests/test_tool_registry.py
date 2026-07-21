"""
Tests for the ToolRegistry and default tool set.

Verifies:
    - Tool registration and lookup.
    - OpenAI function-calling schema generation.
    - Tool execution (success + failure paths).
    - The generate_uuid tool returns valid UUID v4 strings.
    - The read_file/write_file tools sandbox to the workspace.
    - The run_terminal_command tool blocks dangerous patterns.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import uuid

import pytest

from tools.registry import ToolRegistry, create_default_registry


@pytest.fixture
def registry() -> ToolRegistry:
    """Provide a fresh default tool registry for each test."""
    return create_default_registry()


def test_registry_has_default_tools(registry: ToolRegistry) -> None:
    """The default registry must contain all 11 tools (v3.1.0: +revert_file)."""
    names = set(registry.list_names())
    assert names == {
        "read_file", "write_file", "run_terminal_command", "generate_uuid",
        "delegate", "list_background_processes", "kill_background_process",
        "web_search", "code_execution", "file_patch", "revert_file",
    }


def test_registry_has_openai_schemas(registry: ToolRegistry) -> None:
    """get_openai_schemas() must return valid OpenAI function-calling format."""
    schemas = registry.get_openai_schemas()
    assert len(schemas) == 11  # v3.1.0: +revert_file
    for schema in schemas:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_registry_describe(registry: ToolRegistry) -> None:
    """describe() must return a non-empty human-readable catalog."""
    desc = registry.describe()
    assert "read_file" in desc
    assert "generate_uuid" in desc
    assert len(desc) > 50


def test_registry_rejects_duplicate() -> None:
    """Registering the same name twice must raise ValueError."""
    reg = ToolRegistry()

    async def dummy() -> str:
        return "ok"

    reg.register("dummy", dummy, "desc", {"type": "object", "properties": {}, "required": []})
    with pytest.raises(ValueError, match="already registered"):
        reg.register("dummy", dummy, "desc", {"type": "object", "properties": {}, "required": []})


@pytest.mark.asyncio
async def test_generate_uuid_returns_valid_uuid(registry: ToolRegistry) -> None:
    """generate_uuid must return a valid UUID v4 string."""
    result = await registry.execute("generate_uuid")
    assert result.ok is True
    parsed = uuid.UUID(result.output)
    assert parsed.version == 4
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_generate_uuid_is_unique(registry: ToolRegistry) -> None:
    """Two calls to generate_uuid must return different UUIDs."""
    r1 = await registry.execute("generate_uuid")
    r2 = await registry.execute("generate_uuid")
    assert r1.output != r2.output


@pytest.mark.asyncio
async def test_unknown_tool_fails_gracefully(registry: ToolRegistry) -> None:
    """Executing an unregistered tool must return ok=False, not raise."""
    result = await registry.execute("nonexistent_tool")
    assert result.ok is False
    assert "Unknown tool" in result.output


@pytest.mark.asyncio
async def test_write_and_read_file(registry: ToolRegistry) -> None:
    """write_file then read_file must round-trip the content."""
    content = "Hello from Nexa Agent test!"
    write_result = await registry.execute("write_file", path="test_round_trip.txt", content=content)
    assert write_result.ok is True
    assert "wrote" in write_result.output

    read_result = await registry.execute("read_file", path="test_round_trip.txt")
    assert read_result.ok is True
    assert read_result.output == content


@pytest.mark.asyncio
async def test_read_nonexistent_file_fails(registry: ToolRegistry) -> None:
    """Reading a file that doesn't exist must return ok=False with an error message."""
    result = await registry.execute("read_file", path="does_not_exist_12345.txt")
    assert result.ok is False
    # The error message should mention the file or the failure.
    assert "not" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.asyncio
async def test_terminal_command_executes(registry: ToolRegistry) -> None:
    """run_terminal_command must execute a simple echo and return exit code 0."""
    result = await registry.execute("run_terminal_command", command='echo "test123"')
    assert result.ok is True
    assert "exit code: 0" in result.output
    assert "test123" in result.output


@pytest.mark.asyncio
async def test_terminal_command_blocks_dangerous(registry: ToolRegistry) -> None:
    """run_terminal_command must block dangerous command patterns."""
    result = await registry.execute("run_terminal_command", command="rm -rf /")
    assert result.ok is False
    assert "blocked" in result.output.lower()


@pytest.mark.asyncio
async def test_terminal_command_rejects_empty(registry: ToolRegistry) -> None:
    """run_terminal_command must reject empty or whitespace-only commands."""
    result = await registry.execute("run_terminal_command", command="")
    assert result.ok is False
    assert "empty" in result.output.lower()


@pytest.mark.asyncio
async def test_terminal_command_rejects_whitespace(registry: ToolRegistry) -> None:
    """run_terminal_command must reject whitespace-only commands."""
    result = await registry.execute("run_terminal_command", command="   ")
    assert result.ok is False
    assert "empty" in result.output.lower() or "whitespace" in result.output.lower()


@pytest.mark.asyncio
async def test_terminal_command_timeout(registry: ToolRegistry) -> None:
    """run_terminal_command must timeout on long-running commands."""
    result = await registry.execute("run_terminal_command", command="sleep 30")
    assert result.ok is False
    assert "timed out" in result.output.lower() or "timeout" in result.output.lower()
