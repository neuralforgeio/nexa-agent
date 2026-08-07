"""C-02: AI image generation — STUB.

Freezes the interface; no heavy diffusion model backend is bundled. When you
install a backend, keep this signature so callers don't break.
"""
from __future__ import annotations

from typing import Any

IMAGE_GEN_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "Text prompt describing the image."},
        "width": {"type": "integer", "default": 512},
        "height": {"type": "integer", "default": 512},
        "output_path": {"type": "string", "default": "generated.png"},
    },
    "required": ["prompt"],
}


async def image_generation(prompt: str, width: int = 512, height: int = 512, output_path: str = "generated.png", **_: Any) -> str:
    """Stub: raises NotImplementedError until a real backend is wired in."""
    raise NotImplementedError(
        "image_generation is a Category-4 stub. Install an SD backend "
        "(e.g. diffusers + torch) and implement tools/core/image_generation.py."
    )
