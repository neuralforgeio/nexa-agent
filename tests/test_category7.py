"""Category 7 (D-01..D-10) — distribution artifact validation."""
import pytest


def test_dockerfile_exists():
    from pathlib import Path
    text = Path("Dockerfile").read_text(encoding="utf-8")
    assert "FROM python" in text and "EXPOSE 8000" in text


def test_homebrew_formula_parseable():
    from pathlib import Path
    text = Path("packaging/homebrew/nexa-agent.rb").read_text(encoding="utf-8")
    assert "class OpenForgeAgent < Formula" in text and "license" in text


def test_inno_setup_script_sane():
    from pathlib import Path
    text = Path("packaging/windows/inno/nexa.iss").read_text(encoding="utf-8")
    assert "[Setup]" in text and "AppName" in text


def test_vscode_manifest_valid_json():
    import json
    from pathlib import Path
    data = json.loads(Path("extensions/vscode/package.json").read_text(encoding="utf-8"))
    assert data["name"] == "nexa-agent" and "commands" not in data or "contributes" in data


def test_jetbrains_plugin_xml():
    from pathlib import Path
    text = Path("extensions/jetbrains/plugin.xml").read_text(encoding="utf-8")
    assert "<idea-plugin>" in text


def test_pwa_manifest_and_sw():
    import json
    from pathlib import Path
    m = json.loads(Path("openforge_web/public/manifest.json").read_text(encoding="utf-8"))
    assert m["name"] == "Nexa Agent"
    assert Path("openforge_web/public/sw.js").exists()
