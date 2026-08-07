"""C-01: Browser automation via Playwright — STUB.

The Playwright dependency is intentionally NOT installed. The interface is
frozen now so the rest of the system can code against it; the real backend
arrives when you install `playwright` and run `playwright install`.
"""
from __future__ import annotations

from typing import Any

BROWSER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["navigate", "click", "type", "screenshot", "evaluate"]},
        "url":    {"type": "string"},
        "selector": {"type": "string"},
        "text":   {"type": "string"},
    },
    "required": ["action"],
}


INSTALL_HINT = (
    "Browser automation requires Playwright. Install with:\n"
    "  pip install playwright\n"
    "  playwright install\n"
    "Then register a real implementation in tools/core/browser.py."
)


async def browser(action: str, **_: Any) -> str:
    """Stub entry point — always raises NotImplementedError."""
    raise NotImplementedError(INSTALL_HINT)
