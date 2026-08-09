"""
Tests for the Batch 8 skills infrastructure (Phase 1).

Covered:
  * ``validate_schema`` — JSON-Schema subset validator
  * ``parse_manifest``  — happy path + every validation branch
  * ``discover_skills`` / registry — scan, register, get, list
  * ``execute_skill``   — input/output validation, permission gating, disable
  * ``skills._llm``     — provider-agnostic chat + tolerant JSON parsing

The fake providers here are *scripted stand-ins* (deterministic stand-ins for
the LLM boundary only) — all file, schema, and registry logic is exercised for
real. Honest end-to-end LLM coverage lives in ``tests/test_skills_llm_real.py``
under the ``FORGE_E2E_LLAMACPP=1`` gate.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Tuple

import pytest

from skills import registry as R
from skills._llm import chat, chat_json, parse_json_object


# ---------------------------------------------------------------------------
# Scripted provider implementing the chat_stream contract
# ---------------------------------------------------------------------------


class ScriptedProvider:
    """Minimal stand-in implementing the LLMProvider.chat_stream contract."""

    def __init__(self, reply: str = "", events: List[Tuple[str, Any]] | None = None):
        self.reply = reply
        self.events = events
        self.last_messages: List[Dict[str, Any]] | None = None

    async def chat_stream(self, messages, tools=None, registry=None, **kw) -> AsyncGenerator:
        self.last_messages = list(messages)
        if self.events is not None:
            for ev in self.events:
                yield ev
            return
        for i in range(0, len(self.reply), 5):  # emit in small chunks
            yield ("token", self.reply[i : i + 5])
        yield ("done", None)


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------


class TestValidateSchema:
    def test_empty_schema_allows_anything(self):
        assert R.validate_schema({}, {"anything": 1}) == []
        assert R.validate_schema(None, 42) == []

    def test_type_check(self):
        assert R.validate_schema({"type": "string"}, 3) != []
        assert R.validate_schema({"type": "string"}, "ok") == []
        assert R.validate_schema({"type": "integer"}, 3) == []
        # bool must NOT satisfy integer
        assert R.validate_schema({"type": "integer"}, True) != []
        assert R.validate_schema({"type": "number"}, 2.5) == []
        assert R.validate_schema({"type": "number"}, True) != []

    def test_required_and_properties(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "additionalProperties": False,
        }
        assert R.validate_schema(schema, {"name": "a"}) == []
        assert R.validate_schema(schema, {"age": 1}) != []          # missing required
        assert R.validate_schema(schema, {"name": "a", "x": 1}) != []  # unexpected key

    def test_enum_minmax_items_anyof(self):
        assert R.validate_schema({"enum": ["a", "b"]}, "c") != []
        assert R.validate_schema({"minimum": 1, "maximum": 5}, 9) != []
        assert R.validate_schema({"type": "array", "minItems": 2}, [1]) != []
        assert R.validate_schema({"type": "array", "maxItems": 1}, [1, 2]) != []
        ok = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        assert R.validate_schema(ok, "s") == []
        assert R.validate_schema(ok, 7) == []
        assert R.validate_schema(ok, 7.5) != []

    def test_nested_arrays(self):
        schema = {
            "type": "object",
            "properties": {"rows": {"type": "array", "items": {"type": "integer"}}},
        }
        assert R.validate_schema(schema, {"rows": [1, 2]}) == []
        assert R.validate_schema(schema, {"rows": [1, "x"]}) != []


# ---------------------------------------------------------------------------
# parse_manifest
# ---------------------------------------------------------------------------


def _good_manifest() -> Dict[str, Any]:
    return {
        "name": "demo_skill",
        "version": "0.1.0",
        "description": "Demo skill for tests.",
        "category": "code_intelligence",
        "author": "openforge",
        "permissions": ["filesystem:workspace", "memory:read"],
        "input_schema": {"type": "object", "required": ["text"]},
        "output_schema": {"type": "object", "required": ["result"]},
        "examples": [{"input": {"text": "hi"}}],
        "tags": ["demo"],
    }


def _write_manifest(dir_path: Path, data: Dict[str, Any]) -> Path:
    import yaml

    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / "manifest.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


class TestParseManifest:
    def test_happy(self, tmp_path):
        m = R.parse_manifest(_write_manifest(tmp_path / "demo", _good_manifest()))
        assert m.name == "demo_skill"
        assert m.category == "code_intelligence"
        assert m.permissions == ("filesystem:workspace", "memory:read")

    @pytest.mark.parametrize("missing", R.REQUIRED_FIELDS)
    def test_missing_required_field(self, tmp_path, missing):
        data = _good_manifest()
        data.pop(missing)
        with pytest.raises(R.SkillManifestError):
            R.parse_manifest(_write_manifest(tmp_path / "x", data))

    @pytest.mark.parametrize(
        "field,value",
        [
            ("name", "Not Snake"),
            ("name", "1starts-digit"),
            ("version", "1.0"),
            ("version", "v1.0.0"),
            ("description", "   "),
            ("category", "not_a_category"),
            ("permissions", "filesystem:workspace"),  # must be a list
            ("permissions", ["BAD PERM"]),
            ("permissions", ["filesystem:"]),
            ("input_schema", []),
            ("output_schema", None),
        ],
    )
    def test_validation_branches(self, tmp_path, field, value):
        data = _good_manifest()
        data[field] = value
        with pytest.raises(R.SkillManifestError):
            R.parse_manifest(_write_manifest(tmp_path / "y", data))

    def test_not_a_mapping(self, tmp_path):
        p = tmp_path / "z" / "manifest.yaml"
        p.parent.mkdir(parents=True)
        p.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(R.SkillManifestError):
            R.parse_manifest(p)


# ---------------------------------------------------------------------------
# discovery + registry + execution
# ---------------------------------------------------------------------------


class TestDiscoveryAndExecute:
    """Registry discovery/execution. NOTE: these tests repoint ``R._REGISTRY``
    at a throwaway package, so a finalizer always restores the real registry —
    otherwise a later test file (e.g. a skill's executor test) would see an
    empty registry and fail with SkillNotFoundError."""

    @pytest.fixture(autouse=True)
    def _restore_registry(self):
        yield
        R._REGISTRY = R.discover_skills()  # the real ``skills`` package

    def _make_pkg(self, tmp_path: Path, monkeypatch) -> str:
        """Build an importable fake skills package with one real skill."""
        pkg_root = tmp_path / "fake_skills_pkg"
        skill_dir = pkg_root / "code_intelligence" / "echo_skill"
        skill_dir.mkdir(parents=True)
        (pkg_root / "__init__.py").write_text("", encoding="utf-8")
        (pkg_root / "code_intelligence" / "__init__.py").write_text("", encoding="utf-8")

        manifest = _good_manifest()
        manifest["name"] = "echo_skill"
        manifest["input_schema"] = {"type": "object", "required": ["text"],
                                    "properties": {"text": {"type": "string"}}}
        manifest["output_schema"] = {"type": "object", "required": ["echoed"],
                                     "properties": {"echoed": {"type": "string"}}}
        _write_manifest(skill_dir, manifest)

        (skill_dir / "__init__.py").write_text("", encoding="utf-8")
        (skill_dir / "handler.py").write_text(
            "async def handle(input_data, provider):\n"
            "    return {'echoed': input_data['text']}\n",
            encoding="utf-8",
        )

        monkeypatch.syspath_prepend(str(tmp_path))
        return "fake_skills_pkg"

    def test_discover_get_list_execute(self, tmp_path, monkeypatch):
        pkg = self._make_pkg(tmp_path, monkeypatch)
        found = R.discover_skills(pkg)
        assert "echo_skill" in found

        # point the global registry at our fake package for this test
        reg = R.load_registry(pkg)
        assert "echo_skill" in reg
        monkeypatch.setattr(R, "_REGISTRY", reg)

        skill = R.get_skill("echo_skill")
        assert skill.manifest.name == "echo_skill"

        cards = R.list_skills()
        assert any(c["name"] == "echo_skill" and c["enabled"] for c in cards)
        assert R.list_skills(category="web_research") == []

        out = asyncio.run(R.execute_skill("echo_skill", {"text": "hello"}, ScriptedProvider()))
        assert out == {"echoed": "hello"}

    def test_unknown_skill_raises(self):
        with pytest.raises(R.SkillNotFoundError):
            R.get_skill("nope_missing_skill")

    def test_input_validation_blocks(self, tmp_path, monkeypatch):
        pkg = self._make_pkg(tmp_path, monkeypatch)
        monkeypatch.setattr(R, "_REGISTRY", R.load_registry(pkg))
        with pytest.raises(R.SkillInputError):
            asyncio.run(R.execute_skill("echo_skill", {"wrong": 1}, ScriptedProvider()))

    def test_output_validation_blocks(self, tmp_path, monkeypatch):
        pkg_root = tmp_path / "fake_skills_bad"
        skill_dir = pkg_root / "code_intelligence" / "bad_out"
        skill_dir.mkdir(parents=True)
        (pkg_root / "__init__.py").write_text("", encoding="utf-8")
        (pkg_root / "code_intelligence" / "__init__.py").write_text("", encoding="utf-8")
        manifest = _good_manifest()
        manifest["name"] = "bad_out"
        manifest["output_schema"] = {"type": "object", "required": ["must_exist"]}
        _write_manifest(skill_dir, manifest)
        (skill_dir / "__init__.py").write_text("", encoding="utf-8")
        (skill_dir / "handler.py").write_text(
            "async def handle(i, p):\n    return {'other': 1}\n", encoding="utf-8"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.setattr(R, "_REGISTRY", R.load_registry("fake_skills_bad"))
        with pytest.raises(R.SkillOutputError):
            asyncio.run(R.execute_skill("bad_out", {"text": "x"}, ScriptedProvider()))

    def test_disable_toggle(self, tmp_path, monkeypatch):
        pkg = self._make_pkg(tmp_path, monkeypatch)
        monkeypatch.setattr(R, "_REGISTRY", R.load_registry(pkg))
        assert R.is_enabled("echo_skill") is True

        monkeypatch.setenv("FORGE_SKILLS_DISABLED", "echo_skill")
        assert R.is_enabled("echo_skill") is False
        with pytest.raises(R.SkillDisabledError):
            asyncio.run(R.execute_skill("echo_skill", {"text": "x"}, ScriptedProvider()))

        monkeypatch.delenv("FORGE_SKILLS_DISABLED")
        monkeypatch.setenv("FORGE_SKILLS_ENABLED", "something_else")
        assert R.is_enabled("echo_skill") is False


# ---------------------------------------------------------------------------
# _llm adapter
# ---------------------------------------------------------------------------


class TestLLMAdapter:
    def test_chat_concatenates_tokens(self):
        p = ScriptedProvider(reply='{"a": 1, "b": 2}')
        out = asyncio.run(chat(p, "hi", system="sys"))
        assert out == '{"a": 1, "b": 2}'
        assert p.last_messages[0]["role"] == "system"
        assert p.last_messages[-1]["content"] == "hi"

    def test_chat_raises_on_error_event(self):
        p = ScriptedProvider(events=[("error", "boom")])
        with pytest.raises(RuntimeError):
            asyncio.run(chat(p, "hi"))

    def test_chat_rejects_unusable_provider(self):
        with pytest.raises(RuntimeError):
            asyncio.run(chat(object(), "hi"))

    def test_chat_json(self):
        p = ScriptedProvider(reply='```json\n{"result": 42}\n```')
        out = asyncio.run(chat_json(p, "give json"))
        assert out == {"result": 42}

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ('{"a": 1}', {"a": 1}),
            ('prose before {"a": {"b": 2}} prose after', {"a": {"b": 2}}),
            ('```json\n{"x": "y"}\n```', {"x": "y"}),
            ('Here you go: {"s": "he said \\"hi\\" ok"} done', {"s": 'he said "hi" ok'}),
        ],
    )
    def test_parse_json_object_tolerant(self, raw, expected):
        assert parse_json_object(raw) == expected

    @pytest.mark.parametrize("raw", ["no json here", "not {balanced", "[]"])
    def test_parse_json_object_rejects(self, raw):
        with pytest.raises(ValueError):
            parse_json_object(raw)
