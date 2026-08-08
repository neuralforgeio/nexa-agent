"""
Skill: security_audit
=====================

Audit a workspace file — or the readable text/code files under a workspace
directory — for security vulnerabilities (OWASP-style: injection, hardcoded
secrets, unsafe deserialization, path traversal, command execution, weak
crypto, ...). The ``scan_depth`` input (``quick`` | ``deep``) tunes how the
findings are framed and capped. Each finding carries a CWE id, severity,
location, description, and remediation guidance.

Permissions used:
  * ``filesystem:workspace`` — the file or directory referenced by
    ``file_path`` / ``directory_path`` is resolved and read through
    :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``. Directory scans read at most ``_MAX_FILES`` files,
    each truncated to ``_MAX_FILE_CHARS`` characters, to keep the prompt
    sane.
  * ``memory:read`` — declared by the manifest; this handler itself does not
    touch memory.

Honesty note: every finding in ``vulnerabilities`` comes from the model's
reply to a prompt that embeds the *actual* file contents read from disk —
nothing here is stubbed, template-generated, or pre-canned. If the model's
reply is not parseable JSON, ``ValueError`` propagates rather than
fabricating vulnerabilities; LLM errors propagate as ``RuntimeError``.
Audit quality therefore depends on both the model and on the files that were
really read.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle"]

_SCAN_DEPTH_VALUES = ("quick", "deep")

_MAX_FILES = 20
_MAX_FILE_CHARS = 4000
_MAX_TOTAL_CHARS = 40_000

# Quick scans keep the top severities; deep scans keep everything.
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_QUICK_SEVERITIES = ("critical", "high", "medium")
_QUICK_MAX_FINDINGS = 5
_DEEP_MAX_FINDINGS = 50

# Extensions treated as readable text/code when scanning a directory.
_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".conf",
    ".md", ".rst", ".txt",
    ".java", ".kt", ".scala", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".rb", ".php", ".ex", ".exs", ".erl", ".hs", ".lua", ".pl", ".r",
    ".swift", ".m", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".html", ".htm", ".css", ".scss", ".less", ".vue", ".svelte",
    ".sql", ".graphql", ".proto", ".xml", ".dockerfile", ".tf",
}
_TEXT_FILENAMES = {"dockerfile", "makefile", "vagrantfile", "gemfile", "rakefile"}

SYSTEM = (
    "You are Nexa's security-audit engine. You are given the REAL contents of "
    "one or more source files read from the user's workspace, plus a scan "
    "depth (quick | deep). Audit ONLY the code actually shown for OWASP-style "
    "security vulnerabilities: injection (SQL, command, template), hardcoded "
    "secrets or credentials, unsafe deserialization, path traversal, weak or "
    "misused cryptography, broken access control, SSRF, XSS, insecurity "
    "misconfiguration, and similar. Report findings that genuinely exist in "
    "the shown code, referencing the real file and line/region where they "
    "occur. Never invent findings, identifiers, or files. Respond with a "
    "SINGLE JSON object, and nothing else (no markdown fences, no prose "
    "around it), with exactly this key:\n"
    '  "vulnerabilities": an array of objects, each with keys "cwe_id" '
    '(string, e.g. "CWE-89"), "severity" (one of "critical" | "high" | '
    '"medium" | "low" | "info"), "location" (string such as '
    '"app.py:3" naming the real file), "description" (what the '
    "vulnerability is), and \"remediation\" (how to fix it — useful guidance "
    "even when the description is brief). Use an empty array if no genuine "
    "vulnerabilities are present."
)


def _resolve_workspace(rel: str, field: str) -> Path:
    """Resolve ``rel`` inside the workspace, raising SkillInputError."""
    try:
        return Path(tool_api.workspace_path(rel))
    except ValueError as exc:
        raise SkillInputError(f"invalid {field} {rel!r}: {exc}") from exc


def _read_single_file(p: Path, rel: str) -> List[Tuple[str, str]]:
    """Read one workspace file, returning [(label, content)] pairs."""
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"file {rel!r} does not exist in the workspace (resolved to {p})"
        )
    return [(str(p.name), p.read_text(encoding="utf-8", errors="replace"))]


def _iter_text_files(root: Path) -> List[Path]:
    """Collect readable text/code files under ``root`` (sorted, capped)."""
    files: List[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in _TEXT_EXTENSIONS and p.name.lower() not in _TEXT_FILENAMES:
            continue
        files.append(p)
        if len(files) >= _MAX_FILES:
            break
    return files


def _read_directory(root: Path, rel: str) -> List[Tuple[str, str]]:
    """Read the readable text/code files under a workspace directory."""
    if not root.exists() or not root.is_dir():
        raise SkillInputError(
            f"directory {rel!r} does not exist in the workspace (resolved to {root})"
        )
    files = _iter_text_files(root)
    if not files:
        raise SkillInputError(
            f"directory {rel!r} contains no readable text/code files to audit"
        )
    chunks: List[Tuple[str, str]] = []
    total = 0
    for p in files:
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_FILE_CHARS:
            content = content[:_MAX_FILE_CHARS] + "\n# ... [truncated]"
        try:
            label = str(p.relative_to(root.parent))
        except ValueError:
            label = str(p.name)
        chunks.append((label, content))
        total += len(content)
        if total >= _MAX_TOTAL_CHARS:
            break
    return chunks


def _normalise_finding(item: Any) -> Dict[str, Any]:
    """Map a raw model finding to the manifest's per-vulnerability schema."""
    if isinstance(item, dict):
        return {
            "cwe_id": coerce_str(item.get("cwe_id")),
            "severity": coerce_str(item.get("severity"), default="info").lower() or "info",
            "location": coerce_str(item.get("location")),
            "description": coerce_str(item.get("description")),
            "remediation": coerce_str(item.get("remediation")),
        }
    # Non-object finding (e.g. a bare string): keep the content, keep the
    # remediation non-empty so the schema's five keys stay meaningful.
    return {
        "cwe_id": "",
        "severity": "info",
        "location": "",
        "description": coerce_str(item),
        "remediation": "Review and remediate the reported issue.",
    }


async def handle(input_data: dict, provider) -> dict:
    """Audit a workspace file or directory and return structured findings."""
    file_path = input_data.get("file_path")
    directory_path = input_data.get("directory_path")
    if file_path is None and directory_path is None:
        require(input_data, "file_path", str, "path to the file to audit")
    if file_path is not None and not isinstance(file_path, str):
        raise SkillInputError("field 'file_path' must be str")
    if directory_path is not None and not isinstance(directory_path, str):
        raise SkillInputError("field 'directory_path' must be str")

    scan_depth = require(input_data, "scan_depth", str, "scan depth (quick | deep)")
    if scan_depth not in _SCAN_DEPTH_VALUES:
        raise SkillInputError(
            f"scan_depth must be one of {sorted(_SCAN_DEPTH_VALUES)}, got {scan_depth!r}"
        )

    if isinstance(file_path, str) and file_path:
        chunks = _read_single_file(_resolve_workspace(file_path, "file_path"), file_path)
        target_desc = f"the file {file_path!r}"
    else:
        root = _resolve_workspace(directory_path, "directory_path")
        starting = directory_path if str(directory_path).strip() not in ("", ".") else "."
        chunks = _read_directory(root, starting if starting == "." else directory_path)
        target_desc = f"the directory {directory_path!r} ({len(chunks)} file(s) read)"

    listing = "\n\n".join(
        f"### FILE: {label}\n{content}" for label, content in chunks
    )

    prompt = (
        f"Target: {target_desc}\n"
        f"Scan depth: {scan_depth}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{listing}\n-----\n\n"
        f"Perform a '{scan_depth}' security audit of ONLY the code shown "
        "above. Report genuine vulnerabilities present in that code, with "
        "their real locations. If none are present, use an empty "
        "vulnerabilities array — do not invent issues.\n\n"
        'Return a single JSON object with key "vulnerabilities" (array of '
        'objects with "cwe_id" [string], "severity" [string], "location" '
        '[string], "description" [string], "remediation" [string]) '
        "describing ONLY the file content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise to the manifest's output_schema so the executor's output
    # validation always sees well-typed values, regardless of how chatty or
    # sparse the model's raw reply was. Content itself (which vulnerabilities,
    # where, what they say) always comes from the model's reply about the
    # real code — only the TYPES are normalised here.
    findings: List[Dict[str, Any]] = [
        _normalise_finding(item) for item in as_list(data.get("vulnerabilities"))
    ]

    # scan_depth tunes the frame without hiding high-severity findings:
    # quick keeps only severe findings (capped); deep keeps everything.
    if scan_depth == "quick":
        findings = [f for f in findings if f["severity"] in _QUICK_SEVERITIES][
            :_QUICK_MAX_FINDINGS
        ]
    else:
        findings.sort(key=lambda f: _SEVERITY_ORDER.get(f["severity"], 9))
        findings = findings[:_DEEP_MAX_FINDINGS]

    return {"vulnerabilities": findings}
