"""Read a .xlsx spreadsheet: per-sheet header + rows. Uses openpyxl (already a dep)."""
from __future__ import annotations

from typing import Any

from tools._paths import resolve_in_workspace

try:
    import openpyxl
except Exception:  # pragma: no cover
    openpyxl = None  # type: ignore[assignment]

READ_XLSX_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Workspace-relative path to the .xlsx file."},
        "max_rows": {"type": "integer", "description": "Cap on rows per sheet (default 200).", "default": 200},
    },
    "required": ["path"],
}


async def read_xlsx(path: str, max_rows: int = 200, **_: Any) -> str:
    """Extract rows per sheet, first row treated as the header."""
    if openpyxl is None:
        return "read_xlsx requires the 'openpyxl' package (pip install openpyxl)."
    full = resolve_in_workspace(path)
    if not full.exists():
        raise ValueError(f"file not found: '{path}'")
    wb = openpyxl.load_workbook(str(full), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"=== sheet: {ws.title} ===")
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            if i > max(1, int(max_rows)):
                out.append(f"…[truncated at {max_rows} rows]")
                break
            out.append(" | ".join("" if c is None else str(c) for c in row))
    wb.close()
    return "\n".join(out) or "(empty workbook)"
