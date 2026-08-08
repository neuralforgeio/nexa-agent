"""Category 4 (C-01..C-05) — browser/creative/VLM tests + UI smoke.

Covers the backend stubs (C-01/C-02), the VLM path (C-03), and the frontend
mic/TTS additions (C-04/C-05 smoke via presence of new handlers).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from tools.registry import create_default_registry


def test_category4_tools_registered():
    reg = create_default_registry()
    for name in ["browser", "image_generation", "image_understanding"]:
        assert reg.has(name), name


@pytest.mark.asyncio
async def test_browser_stub_raises_not_implemented():
    from tools.core.browser import browser

    with pytest.raises(NotImplementedError):
        await browser("navigate", url="https://example.com")


@pytest.mark.asyncio
async def test_image_generation_stub_raises_not_implemented():
    from tools.core.image_generation import image_generation

    with pytest.raises(NotImplementedError):
        await image_generation("a red square")


@pytest.mark.asyncio
async def test_image_understanding_missing_file_error(tmp_path, monkeypatch):
    from tools.core.image_understanding import image_understanding

    monkeypatch.setattr("tools.core.image_understanding.resolve_in_workspace", lambda p: tmp_path / p)
    with pytest.raises(ValueError):
        await image_understanding("nope.png")


@pytest.mark.asyncio
async def test_image_understanding_ok(tmp_path, monkeypatch):
    # Minimal valid 1x1 PNG
    import base64

    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    img = tmp_path / "dot.png"
    img.write_bytes(base64.b64decode(png_b64))
    from tools.core.image_understanding import image_understanding

    monkeypatch.setattr("tools.core.image_understanding.resolve_in_workspace", lambda p: tmp_path / p)
    out = await image_understanding("dot.png", "What is it?")
    assert "dot.png" in out and "What is it?" in out


def test_voice_and_tts_mentions_present():
    """Smoke: Composer exposes the mic button; MessageBubble exposes TTS."""
    from pathlib import Path

    composer = (Path("openforge_web") / "components" / "Composer.tsx").read_text(encoding="utf-8")
    bubble = (Path("openforge_web") / "components" / "MessageBubble.tsx").read_text(encoding="utf-8")
    assert "voice-input" in composer and "toggleListening" in composer  # C-04
    assert "speechSynthesis" in bubble and "toggleSpeak" in bubble and "Volume2" in bubble  # C-05
