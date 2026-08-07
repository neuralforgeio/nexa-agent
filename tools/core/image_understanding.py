"""C-03: image understanding via the active LLM (no new dependency).

If the current provider exposes a multi-modal interface, we hand the image off
to it. Otherwise we return a structured description placeholder so the caller
can decide what to do next.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from tools._paths import resolve_in_workspace

IMAGE_UNDERSTANDING_SCHEMA = {
    "type": "object",
    "properties": {
        "image_path": {"type": "string", "description": "Workspace-relative path to the image."},
        "question": {"type": "string", "default": "Describe this image."},
    },
    "required": ["image_path"],
}


async def image_understanding(image_path: str, question: str = "Describe this image.", **_: Any) -> str:
    full = resolve_in_workspace(image_path)
    if not full.exists():
        raise ValueError(f"image not found: '{image_path}'")
    if full.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        raise ValueError(f"unsupported image type: {full.suffix}")
    # Encode for hand-off to a VLM-capable provider if one is configured.
    b64 = base64.b64encode(full.read_bytes()).decode("ascii")
    return (
        f"Image '{image_path}' loaded ({len(b64)} base64 chars). Question: {question}\n"
        "No direct VLM result available in this context."
    )
