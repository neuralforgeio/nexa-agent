"""
Tests for the ``deployment_automation`` skill handler.

This skill is intentionally NOT LLM-backed and NOT deploy-capable: with no
cloud credentials in the environment, the only honest behaviour is to
validate the input, confirm the app path really exists in the workspace, and
return a schema-valid result that states plainly that nothing was deployed.

Honesty invariants under test: ``deployment_url`` and ``rollback_command``
are empty, ``logs`` says no deploy was attempted, and the workspace is left
byte-for-byte unchanged.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.devops_operations.deployment_automation.handler import handle
from tests._skill_helpers import ScriptedProvider

VALID_CONFIG = {"env": "production", "build_command": "npm run build"}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "apps" / "web-dashboard").mkdir(parents=True)
    (tmp_path / "apps" / "web-dashboard" / "package.json").write_text(
        '{"name": "web-dashboard"}\n', encoding="utf-8"
    )
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # nexa.config.NEXA_WORKSPACE is captured at import time, so the env var
    # alone is not enough — repoint the already-imported reference used by
    # tools._paths.resolve_in_workspace (same pattern as test_skills_code_*).
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("deployment_automation").manifest


def _input(**over):
    base = {
        "app_path": "apps/web-dashboard",
        "target": "vercel",
        "config": VALID_CONFIG,
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_input_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(_input(config=None), ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(_input(target="flyio"), ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Missing app path raises honest input error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_app_path_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(_input(app_path="apps/nope"), ScriptedProvider())


# ---------------------------------------------------------------------------
# 3. Honest stub: schema-valid AND truthful that nothing was deployed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_stub_schema_valid_and_states_no_deploy(ws):
    out = await handle(_input(), ScriptedProvider())

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert set(out.keys()) == {"deployment_url", "logs", "rollback_command"}
    # Truthful, not fake:
    assert out["deployment_url"] == ""
    assert "no actual deploy was attempted" in out["logs"]
    assert "requires cloud credentials not provided" in out["logs"]
    assert out["rollback_command"] == ""
    # The real app path and target are reflected in the logs.
    assert "vercel" in out["logs"]
    assert "web-dashboard" in out["logs"]


@pytest.mark.asyncio
async def test_workspace_is_untouched(ws):
    pkg = ws / "apps" / "web-dashboard" / "package.json"
    before = pkg.read_text(encoding="utf-8")
    await handle(_input(), ScriptedProvider())
    assert pkg.read_text(encoding="utf-8") == before
    # No stray deploy artefacts were created anywhere in the workspace.
    # NOTE: build the expected list with os.path.join so this is portable —
    # hardcoded backslashes fail on Linux/macOS where rglob yields '/'.
    import os
    expected = sorted([
        "apps",
        os.path.join("apps", "web-dashboard"),
        os.path.join("apps", "web-dashboard", "package.json"),
    ])
    assert sorted(str(p.relative_to(ws)) for p in ws.rglob("*")) == expected


# ---------------------------------------------------------------------------
# 4. Full executor path validates, and invalid enum is rejected by the
#    registry before the handler runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "deployment_automation", _input(), ScriptedProvider()
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["deployment_url"] == ""
    assert "no actual deploy was attempted" in out["logs"]


@pytest.mark.asyncio
async def test_execute_skill_rejects_bad_target_before_handler(ws):
    with pytest.raises(R.SkillInputError):
        await skills.execute_skill(
            "deployment_automation",
            _input(target="flyio"),
            ScriptedProvider(),
        )
