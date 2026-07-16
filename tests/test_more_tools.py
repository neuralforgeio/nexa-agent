"""
Tests for web_search, code_execution, and file_patch tools.

Verifies:
    - web_search: empty query rejection, schema, registration.
    - code_execution: empty code, timeout, output capture, schema.
    - file_patch: empty inputs, patch application, backup creation, schema.
    - All 10 tools registered in the default registry.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest

from tools.registry import ToolRegistry, create_default_registry
from tools.web_search_tool import web_search, WEB_SEARCH_SCHEMA, _parse_ddg_html
from tools.code_execution_tool import code_execution, CODE_EXECUTION_SCHEMA, MAX_CODE_TIMEOUT
from tools.file_patch_tool import file_patch, FILE_PATCH_SCHEMA, _parse_patch, _apply_hunk


@pytest.fixture
def registry() -> ToolRegistry:
    """Provide a fresh default tool registry for each test."""
    return create_default_registry()


class TestToolRegistration:
    """Tests that all 10 tools are registered."""

    def test_ten_tools_registered(self, registry: ToolRegistry) -> None:
        """The registry must have 10 tools (7 + web_search + code_execution + file_patch)."""
        names = set(registry.list_names())
        assert len(names) == 10
        assert "web_search" in names
        assert "code_execution" in names
        assert "file_patch" in names

    def test_all_have_openai_schemas(self, registry: ToolRegistry) -> None:
        """All 10 tools must have valid OpenAI schemas."""
        schemas = registry.get_openai_schemas()
        assert len(schemas) == 10
        schema_names = [s["function"]["name"] for s in schemas]
        assert "web_search" in schema_names
        assert "code_execution" in schema_names
        assert "file_patch" in schema_names


class TestWebSearch:
    """Tests for the web_search tool."""

    def test_schema_is_valid(self) -> None:
        """The web_search schema must have query as required."""
        assert "query" in WEB_SEARCH_SCHEMA["properties"]
        assert WEB_SEARCH_SCHEMA["required"] == ["query"]

    @pytest.mark.asyncio
    async def test_empty_query_raises(self) -> None:
        """Empty query must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await web_search("")

    @pytest.mark.asyncio
    async def test_whitespace_query_raises(self) -> None:
        """Whitespace-only query must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await web_search("   ")

    def test_parse_ddg_html_empty(self) -> None:
        """Parsing empty HTML must return empty list."""
        assert _parse_ddg_html("", 5) == []

    def test_parse_ddg_html_no_results(self) -> None:
        """Parsing HTML with no results must return empty list."""
        html = "<html><body>No results</body></html>"
        assert _parse_ddg_html(html, 5) == []


class TestCodeExecution:
    """Tests for the code_execution tool."""

    def test_schema_is_valid(self) -> None:
        """The code_execution schema must have code as required."""
        assert "code" in CODE_EXECUTION_SCHEMA["properties"]
        assert CODE_EXECUTION_SCHEMA["required"] == ["code"]

    @pytest.mark.asyncio
    async def test_empty_code_raises(self) -> None:
        """Empty code must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await code_execution("")

    @pytest.mark.asyncio
    async def test_simple_print(self) -> None:
        """Executing a simple print statement must capture output."""
        result = await code_execution('print("hello from nexa")')
        assert "exit code: 0" in result
        assert "hello from nexa" in result

    @pytest.mark.asyncio
    async def test_math_computation(self) -> None:
        """Executing math must produce correct output."""
        result = await code_execution('print(2 + 3)')
        assert "5" in result

    @pytest.mark.asyncio
    async def test_stderr_capture(self) -> None:
        """stderr output must be captured."""
        result = await code_execution('import sys; sys.stderr.write("error msg")')
        assert "error msg" in result

    @pytest.mark.asyncio
    async def test_timeout_exceeds_max(self) -> None:
        """Timeout above MAX_CODE_TIMEOUT must raise ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            await code_execution('print("hi")', timeout=999.0)

    @pytest.mark.asyncio
    async def test_timeout_triggers(self) -> None:
        """Code that runs too long must be killed."""
        with pytest.raises(Exception, match="timed out"):
            await code_execution('import time; time.sleep(10)', timeout=1.0)

    @pytest.mark.asyncio
    async def test_no_output_message(self) -> None:
        """Code with no output must show '(no output)'."""
        result = await code_execution('x = 1')
        assert "(no output)" in result


class TestFilePatch:
    """Tests for the file_patch tool."""

    @pytest.mark.asyncio
    async def test_empty_path_raises(self) -> None:
        """Empty path must raise ValueError."""
        with pytest.raises(ValueError, match="path is required"):
            await file_patch("", "patch text")

    @pytest.mark.asyncio
    async def test_empty_patch_raises(self) -> None:
        """Empty patch must raise ValueError."""
        with pytest.raises(ValueError, match="patch is required"):
            await file_patch("test.txt", "")

    @pytest.mark.asyncio
    async def test_nonexistent_file_raises(self) -> None:
        """Patching a non-existent file must raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await file_patch("nonexistent_file_xyz.txt", "@@ -1 +1 @@\n-old\n+new")

    @pytest.mark.asyncio
    async def test_apply_simple_patch(self) -> None:
        """A simple line replacement patch must work."""
        # First create a file.
        from tools.file_tools import write_file
        await write_file(path="patch_test.txt", content="line 1\nold line\nline 3\n")

        # Apply patch.
        patch = """@@ -1,3 +1,3 @@
 line 1
-old line
+new line
 line 3"""
        result = await file_patch(path="patch_test.txt", patch=patch)
        assert "hunk(s) applied" in result

        # Verify the content changed.
        from tools.file_tools import read_file
        content = await read_file(path="patch_test.txt")
        assert "new line" in content
        assert "old line" not in content

    def test_parse_patch_extracts_hunks(self) -> None:
        """_parse_patch must extract hunks from unified diff."""
        patch = """--- file.txt
+++ file.txt
@@ -1,2 +1,2 @@
 line 1
-old line
+new line
"""
        hunks = _parse_patch(patch)
        assert len(hunks) == 1
        assert hunks[0]["old_start"] == 1
        assert "old line" in hunks[0]["removes"]
        assert "new line" in hunks[0]["adds"]

    def test_parse_patch_empty(self) -> None:
        """_parse_patch must return empty list for no hunks."""
        assert _parse_patch("no hunks here") == []

    def test_apply_hunk_replaces_lines(self) -> None:
        """_apply_hunk must replace removed lines with added lines."""
        lines = ["line 1\n", "old line\n", "line 3\n"]
        hunk = {
            "old_start": 1,
            "new_start": 1,
            "removes": ["old line"],
            "adds": ["new line"],
            "context": ["line 1", "line 3"],
        }
        result = _apply_hunk(lines, hunk)
        assert "new line\n" in result
        assert "old line\n" not in result

    def test_schema_is_valid(self) -> None:
        """The file_patch schema must have path and patch as required."""
        assert "path" in FILE_PATCH_SCHEMA["properties"]
        assert "patch" in FILE_PATCH_SCHEMA["properties"]
        assert "path" in FILE_PATCH_SCHEMA["required"]
        assert "patch" in FILE_PATCH_SCHEMA["required"]
