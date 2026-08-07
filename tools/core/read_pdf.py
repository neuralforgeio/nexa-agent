"""Read a PDF file from the workspace and return its text, page by page.

Tool id: ``read_pdf`` — extracts per-page text via pypdf.
"""
from __future__ import annotations

from typing import Any

from nexa.config import NEXA_WORKSPACE
from tools._paths import resolve_in_workspace

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dep
    PdfReader = None  # type: ignore[assignment]

READ_PDF_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Workspace-relative path to the .pdf file."},
        "max_pages": {"type": "integer", "description": "Cap on pages to read (default 50).", "default": 50},
    },
    "required": ["path"],
}


async def read_pdf(path: str, max_pages: int = 50, **_: Any) -> str:
    """Extract text from a PDF, one ``--- page N ---`` section per page."""
    if PdfReader is None:
        return "read_pdf requires the 'pypdf' package (pip install pypdf)."
    full = resolve_in_workspace(path)
    if not full.exists():
        raise ValueError(f"file not found: '{path}'")
    if full.suffix.lower() != ".pdf":
        raise ValueError(f"not a .pdf file: '{path}'")
    try:
        reader = PdfReader(str(full))
        out = []
        for i, page in enumerate(reader.pages[: max(1, int(max_pages))], 1):
            out.append(f"--- page {i} ---\n{page.extract_text() or ''}")
        return "\n\n".join(out) or "(no extractable text)"
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"could not read pdf '{path}': {exc}") from exc
