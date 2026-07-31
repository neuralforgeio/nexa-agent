"""
Tests for the 20 v4.0.0 planning tools + the user-tool loader.
"""

import os
import pytest

from tools.planning.todos import (
    task_plan, todo_write, todo_read,
    TASK_PLAN_SCHEMA, TODO_WRITE_SCHEMA, TODO_READ_SCHEMA,
)
from tools.planning.scratchpad import (
    scratchpad_write, think,
    SCRATCHPAD_WRITE_SCHEMA, THINK_SCHEMA,
)
from tools.planning.fs_intelligence import (
    list_directory, search_files, file_info, project_scaffold,
    LIST_DIRECTORY_SCHEMA, SEARCH_FILES_SCHEMA, FILE_INFO_SCHEMA,
    PROJECT_SCAFFOLD_SCHEMA,
)
from tools.planning.git_tools import (
    git_status, git_diff, git_log, git_checkpoint,
    GIT_STATUS_SCHEMA, GIT_DIFF_SCHEMA, GIT_LOG_SCHEMA, GIT_CHECKPOINT_SCHEMA,
)
from tools.planning.process_tools import (
    list_ports, process_snapshot, LIST_PORTS_SCHEMA, PROCESS_SNAPSHOT_SCHEMA,
)
from tools.planning.knowledge_tools import (
    memory_search, session_search, MEMORY_SEARCH_SCHEMA, SESSION_SEARCH_SCHEMA,
    web_fetch, WEB_FETCH_SCHEMA,
)
from tools.planning.self_extend import (
    create_tool, plan_and_delegate, CREATE_TOOL_SCHEMA, PLAN_AND_DELEGATE_SCHEMA,
)


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------
class TestPlanningToolsRegistered:
    def test_all_twenty_planning_tools_in_default_registry(self):
        from tools.registry import create_default_registry
        r = create_default_registry()
        expected = {
            "task_plan", "todo_write", "todo_read", "scratchpad_write", "think",
            "list_directory", "search_files", "file_info", "project_scaffold",
            "git_status", "git_diff", "git_log", "git_checkpoint",
            "list_ports", "process_snapshot",
            "memory_search", "session_search", "web_fetch",
            "create_tool", "plan_and_delegate",
        }
        assert expected.issubset(set(r.list_names()))

    def test_total_tool_count_is_33(self):
        from tools.registry import create_default_registry
        r = create_default_registry()
        assert len(r.list_names()) == 33

    def test_all_have_openai_schemas(self):
        from tools.registry import create_default_registry
        r = create_default_registry()
        schemas = {s["function"]["name"] for s in r.get_openai_schemas()}
        for name in r.list_names():
            assert name in schemas


# ---------------------------------------------------------------------------
# task_plan
# ---------------------------------------------------------------------------
class TestTaskPlan:
    @pytest.mark.asyncio
    async def test_web_app_template(self):
        out = await task_plan("Build an ecommerce webapp with Next.js")
        assert "web-app" in out
        assert "scaffold" in out.lower()

    @pytest.mark.asyncio
    async def test_bug_fix_template(self):
        out = await task_plan("Fix the login crash regression")
        assert "bug-fix" in out
        assert "reproduce" in out.lower()

    @pytest.mark.asyncio
    async def test_generic_template(self):
        out = await task_plan("Organize my photos")
        assert "generic" in out

    @pytest.mark.asyncio
    async def test_empty_goal(self):
        out = await task_plan("   ")
        assert "Error" in out

    @pytest.mark.asyncio
    async def test_max_steps_clamped(self):
        out = await task_plan("Build a website", max_steps=4)
        # Should have at most 4 numbered items.
        import re
        assert len(re.findall(r"^\d+\.\s+\[", out, re.M)) <= 4


# ---------------------------------------------------------------------------
# TODOs
# ---------------------------------------------------------------------------
class TestTodos:
    @pytest.mark.asyncio
    async def test_write_then_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.todos.resolve_in_workspace", lambda p: tmp_path)
        await todo_write(["write tests", "ship it"], name="proj1")
        out = await todo_read("proj1")
        assert "write tests" in out
        assert "ship it" in out
        assert "2 remaining" in out

    @pytest.mark.asyncio
    async def test_mark_checked(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.todos.resolve_in_workspace", lambda p: tmp_path)
        await todo_write(["a", "b"], name="t", checked=["a"])
        out = await todo_read("t")
        assert "[x] a" in out
        assert "[ ] b" in out
        assert "1 done" in out and "1 remaining" in out

    @pytest.mark.asyncio
    async def test_read_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.todos.resolve_in_workspace", lambda p: tmp_path)
        await todo_write(["x"], name="one")
        await todo_write(["y"], name="two")
        out = await todo_read("")
        assert "one" in out and "two" in out

    @pytest.mark.asyncio
    async def test_read_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.todos.resolve_in_workspace", lambda p: tmp_path)
        out = await todo_read("nope")
        assert "not found" in out


# ---------------------------------------------------------------------------
# Scratchpad + think
# ---------------------------------------------------------------------------
class TestScratchpad:
    @pytest.mark.asyncio
    async def test_append_and_replace(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.scratchpad.resolve_in_workspace", lambda p: tmp_path)
        await scratchpad_write("first", mode="replace")
        await scratchpad_write("second", mode="append", label="note")
        content = (tmp_path / ".nexa" / "scratchpad.md").read_text()
        assert "first" in content and "second" in content and "## note" in content

    @pytest.mark.asyncio
    async def test_empty_content(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.scratchpad.resolve_in_workspace", lambda p: tmp_path)
        out = await scratchpad_write("   ")
        assert "Error" in out

    @pytest.mark.asyncio
    async def test_think_echoes(self):
        out = await think("Should I patch or rewrite?", next_action="file_patch", confidence=0.7)
        assert "Should I patch or rewrite?" in out
        assert "file_patch" in out
        assert "70%" in out

    @pytest.mark.asyncio
    async def test_think_confidence_clamped(self):
        out = await think("t", confidence=5.0)
        assert "100%" in out


# ---------------------------------------------------------------------------
# Filesystem intelligence
# ---------------------------------------------------------------------------
class TestFSIntelligence:
    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print(1)")
        (tmp_path / "README.md").write_text("# x")
        out = await list_directory(".", depth=2)
        assert "src/" in out and "app.py" in out and "README.md" in out

    @pytest.mark.asyncio
    async def test_list_directory_excludes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "junk.js").write_text("x")
        (tmp_path / "keep.py").write_text("x")
        out = await list_directory(".", depth=2)
        assert "keep.py" in out
        assert "junk.js" not in out

    @pytest.mark.asyncio
    async def test_search_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        (tmp_path / "a.py").write_text("def hello():\n    pass\n")
        (tmp_path / "b.txt").write_text("nothing here\n")
        out = await search_files("hello", ".", file_glob="*.py")
        assert "a.py" in out and "hello" in out

    @pytest.mark.asyncio
    async def test_search_files_literal(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        (tmp_path / "c.txt").write_text("price is $5.00\n")
        out = await search_files("$5.00", ".", regex=False)
        assert "c.txt" in out

    @pytest.mark.asyncio
    async def test_file_info(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        f = tmp_path / "info.txt"
        f.write_text("line1\nline2\n")
        out = await file_info("info.txt")
        assert "Lines" in out and "2" in out and "SHA-256" in out

    @pytest.mark.asyncio
    async def test_project_scaffold_next(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        out = await project_scaffold("My Shop", kind="next")
        assert "My Shop" in out
        assert (tmp_path / "my-shop" / "package.json").exists()
        assert (tmp_path / "my-shop" / "app" / "page.tsx").exists()

    @pytest.mark.asyncio
    async def test_project_scaffold_invalid_kind(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.fs_intelligence.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        out = await project_scaffold("X", kind="cobol")
        assert "Error" in out


# ---------------------------------------------------------------------------
# Git tools
# ---------------------------------------------------------------------------
class TestGitTools:
    @pytest.fixture
    def repo(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.git_tools.resolve_in_workspace", lambda p: tmp_path / p if p != "." else tmp_path)
        import subprocess
        for args in (["init"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=tmp_path, capture_output=True)
        (tmp_path / "a.txt").write_text("hello")
        return tmp_path

    @pytest.mark.asyncio
    async def test_git_status_not_repo(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.git_tools.resolve_in_workspace", lambda p: tmp_path)
        out = await git_status(".")
        assert "not a git repo" in out

    @pytest.mark.asyncio
    async def test_git_checkpoint_flow(self, repo):
        out = await git_status(".")
        assert "Branch" in out
        cp = await git_checkpoint(".", message="init")
        assert "Checkpoint created" in cp
        st = await git_status(".")
        assert "clean" in st.lower()
        log = await git_log(".", limit=5)
        assert "checkpoint" in log.lower()

    @pytest.mark.asyncio
    async def test_git_diff_empty(self, repo):
        out = await git_diff(".")
        assert "diff" in out.lower() or "no unstaged" in out.lower() or "No unstaged" in out


# ---------------------------------------------------------------------------
# Process tools
# ---------------------------------------------------------------------------
class TestProcessTools:
    @pytest.mark.asyncio
    async def test_list_ports_reports_something(self):
        out = await list_ports()
        assert isinstance(out, str) and len(out) > 10

    @pytest.mark.asyncio
    async def test_process_snapshot_matches_python(self):
        out = await process_snapshot(name_filter="python")
        # Should find at least this test's own python process.
        assert "python" in out.lower()

    @pytest.mark.asyncio
    async def test_process_snapshot_no_match(self):
        out = await process_snapshot(name_filter="definitely-not-a-real-process-xyz")
        assert "No processes" in out or ("0" in out and "matching" in out)


# ---------------------------------------------------------------------------
# Knowledge tools (use a temp NEXA_HOME via env)
# ---------------------------------------------------------------------------
class TestKnowledgeTools:
    @pytest.mark.asyncio
    async def test_memory_search_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEXA_HOME", str(tmp_path))
        # Re-import state to pick up the env var? state reads NEXA_HOME at import.
        # Instead we just confirm graceful handling of a fresh empty DB.
        out = await memory_search("anything")
        assert "No memories" in out or "matching" in out

    @pytest.mark.asyncio
    async def test_session_search_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEXA_HOME", str(tmp_path))
        out = await session_search("anything")
        assert isinstance(out, str)

    @pytest.mark.asyncio
    async def test_web_fetch_rejects_bad_scheme(self):
        out = await web_fetch("ftp://example.com")
        assert "Error" in out


# ---------------------------------------------------------------------------
# Self-extension
# ---------------------------------------------------------------------------
class TestSelfExtend:
    @pytest.mark.asyncio
    async def test_create_tool_writes_and_loads(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.self_extend._config.NEXA_HOME", tmp_path)
        out = await create_tool(
            name="greet",
            description="Greet someone",
            parameters=["who"],
            body='    return f"Hello, {who}!"',
        )
        assert "greet" in out
        tool_file = tmp_path / "tools" / "greet.py"
        assert tool_file.exists()
        assert "async def greet" in tool_file.read_text()

    @pytest.mark.asyncio
    async def test_create_tool_invalid_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.planning.self_extend._config.NEXA_HOME", tmp_path)
        out = await create_tool(name="not a python name!!", description="x")
        assert "Error" in out

    @pytest.mark.asyncio
    async def test_user_tool_loader_picks_up(self, tmp_path, monkeypatch):
        # Patch the config module FIRST — both self_extend and registry read
        # NEXA_HOME from this module at call time. The monkeypatch fixture
        # automatically restores the original value at test teardown.
        monkeypatch.setattr("nexa.config.NEXA_HOME", tmp_path)
        await create_tool(name="echo_test", description="echo", parameters=["msg"],
                          body='    return "echo: " + msg')
        import tools.registry as regmod
        r = regmod.ToolRegistry()
        regmod.load_user_tools(r)
        assert r.has("echo_test")
        res = await r.execute("echo_test", msg="hi")
        assert res.ok and "echo: hi" in res.output

    @pytest.mark.asyncio
    async def test_plan_and_delegate(self):
        out = await plan_and_delegate("Build a portfolio site", max_steps=5)
        assert "delegate" in out.lower()
        assert "Step 1" in out
