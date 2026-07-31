"""
Nexa Agent — Planning Tools: Filesystem Intelligence (v4.0.0)
=============================================================

Four tools:

- :func:`list_directory`  — tree-style listing with sizes and glob excludes.
- :func:`search_files`    — recursive regex search over workspace text files.
- :func:`file_info`       — size, mtime, line count, sha256, MIME guess.
- :func:`project_scaffold`— generate starter code for common project types.

All are workspace-scoped via :func:`tools._paths.resolve_in_workspace`.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import fnmatch
import hashlib
import mimetypes
import os
import re
import stat as _stat
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tools._paths import MAX_FILE_SIZE, resolve_in_workspace as _resolve_in_workspace


def resolve_in_workspace(raw: str):
    """Module-level wrapper so tests can monkeypatch path resolution."""
    return _resolve_in_workspace(raw)


# Directories we never descend into (huge, noisy, or irrelevant).
_SKIP_DIRS = {
    "node_modules", ".git", ".next", "__pycache__", ".pytest_cache",
    ".venv", "venv", "dist", "build", ".turbo", "coverage",
}


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------
def _human_size(n: int) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


async def list_directory(
    path: str = ".",
    depth: int = 3,
    exclude: Optional[List[str]] = None,
    show_sizes: bool = True,
    max_entries: int = 200,
) -> str:
    """
    Produce a tree-style listing of a workspace directory.

    Args:
        path:        Workspace-relative directory (default ``"."``).
        depth:       How many directory levels to recurse (1–8, default 3).
        exclude:     Glob patterns to skip (e.g. ``["*.log", "node_modules"]``).
        show_sizes:  Include file sizes (default True).
        max_entries: Total entries to emit before truncating (default 200).

    Returns:
        A monospace-art directory tree as Markdown.
    """
    exclude = list(exclude or []) + list(_SKIP_DIRS)
    try:
        root = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not root.exists():
        return f"**Not found:** `{path}`"
    if not root.is_dir():
        return f"**Not a directory:** `{path}`"

    depth = max(1, min(depth, 8))
    lines: List[str] = [f"```", f"{path or '.'}/"]
    count = 0

    def _excluded(name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in exclude)

    def _walk(d: Path, prefix: str, remaining: int) -> None:
        nonlocal count
        if remaining < 0 or count >= max_entries:
            return
        try:
            children = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            lines.append(f"{prefix}└── <unreadable>")
            return

        visible = [c for c in children if not _excluded(c.name)]
        for i, child in enumerate(visible):
            if count >= max_entries:
                lines.append(f"{prefix}└── … ({len(visible) - i} more)")
                return
            is_last = i == len(visible) - 1
            branch = "└── " if is_last else "├── "
            count += 1
            if child.is_dir():
                lines.append(f"{prefix}{branch}{child.name}/")
                if remaining > 0:
                    _walk(child, prefix + ("    " if is_last else "│   "), remaining - 1)
            else:
                size = f"  {_human_size(child.stat().st_size)}" if show_sizes else ""
                lines.append(f"{prefix}{branch}{child.name}{size}")

    _walk(root, "", depth)
    lines.append("```")
    if count >= max_entries:
        lines.append(f"_Truncated at {max_entries} entries._")
    return "\n".join(lines)


LIST_DIRECTORY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Workspace-relative directory.", "default": "."},
        "depth": {"type": "integer", "description": "Recursion depth (1-8).", "default": 3},
        "exclude": {"type": "array", "items": {"type": "string"}, "description": "Glob patterns to skip."},
        "show_sizes": {"type": "boolean", "default": True},
        "max_entries": {"type": "integer", "default": 200},
    },
    "required": [],
}


# ---------------------------------------------------------------------------
# search_files
# ---------------------------------------------------------------------------
_MAX_SEARCH_BYTES = 256 * 1024  # 256 KB cap per file


async def search_files(
    query: str,
    path: str = ".",
    file_glob: Optional[str] = None,
    regex: bool = True,
    case_sensitive: bool = False,
    context_lines: int = 0,
    max_results: int = 50,
) -> str:
    """
    Recursively search text files in the workspace.

    Args:
        query:          The search pattern (regex by default).
        path:           Workspace-relative root (default ".").
        file_glob:      Optional glob filter, e.g. ``"*.py"``. Comma-separated
                        globs also work (``"*.ts,*.tsx"``).
        regex:          Treat ``query`` as regex (default True, else literal).
        case_sensitive: Case-sensitive matching (default False).
        context_lines:  Lines of context around each match (0–5).
        max_results:    Maximum number of matches to report (default 50).

    Returns:
        Match report as Markdown, with each match shown as
        ``path:line: content`` plus optional context lines.
    """
    if not query:
        return "**Error.** `query` cannot be empty."

    try:
        root = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not root.exists():
        return f"**Not found:** `{path}`"

    globs = [g.strip() for g in (file_glob or "").split(",") if g.strip()]

    flags = 0 if case_sensitive else re.IGNORECASE
    if not regex:
        query = re.escape(query)
    try:
        pattern = re.compile(query, flags)
    except re.error as exc:
        return f"**Invalid regex:** {exc}"

    context_lines = max(0, min(context_lines, 5))
    matches: List[str] = []
    files_searched = 0
    total_size = 0

    # v4.1.0: offload the blocking ``os.walk`` tree traversal to a worker
    # thread so slow/disk-heavy searches don't freeze the asyncio loop.
    import asyncio as _asyncio

    def _walk_list(root: Path) -> List[tuple]:
        results = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            results.append((dirpath, list(dirnames), list(filenames)))
        return results

    try:
        # Run inside the calling event loop if there is one; fall back to a
        # new loop when called from a thread without one.
        loop = _asyncio.get_running_loop()
        tree = await loop.run_in_executor(None, _walk_list, root)
    except RuntimeError:
        tree = _walk_list(root)

    for dirpath, _dirnames, filenames in tree:
        # _walk_list already filtered dirnames (skips .git/node_modules etc).
        for fname in filenames:
            if len(matches) >= max_results:
                break
            if globs and not any(fnmatch.fnmatch(fname, g) for g in globs):
                continue
            fpath = Path(dirpath) / fname
            try:
                if fpath.stat().st_size > _MAX_SEARCH_BYTES:
                    continue
                with fpath.open("r", encoding="utf-8", errors="replace") as fh:
                    file_lines = fh.readlines()
            except OSError:
                continue
            files_searched += 1
            total_size += len(file_lines)

            for i, line in enumerate(file_lines, 1):
                if pattern.search(line):
                    rel = fpath.relative_to(root)
                    snippet = [f"**`{rel}:{i}`** — `{line.rstrip()[:200]}`"]
                    if context_lines:
                        lo = max(0, i - 1 - context_lines)
                        hi = min(len(file_lines), i + context_lines)
                        for ctx_i in range(lo, hi):
                            if ctx_i == i - 1:
                                continue
                            snippet.append(f"  {ctx_i + 1:>4}: {file_lines[ctx_i].rstrip()}")
                    matches.append("\n".join(snippet))
                    if len(matches) >= max_results:
                        break

    if not matches:
        return (
            f"No matches for `{query}` in `{path or '.'}` "
            f"({files_searched} files searched)."
        )

    header = (
        f"Found **{len(matches)}** match(es) for `{query}` "
        f"in `{path or '.'}` ({files_searched} files searched):"
    )
    body = "\n\n".join(matches)
    if len(matches) >= max_results:
        body += f"\n\n_Truncated at {max_results} matches._"
    return f"{header}\n\n{body}"


SEARCH_FILES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Pattern to search for."},
        "path": {"type": "string", "default": "."},
        "file_glob": {"type": "string", "description": "Optional glob filter, e.g. '*.py' or '*.ts,*.tsx'."},
        "regex": {"type": "boolean", "default": True},
        "case_sensitive": {"type": "boolean", "default": False},
        "context_lines": {"type": "integer", "default": 0},
        "max_results": {"type": "integer", "default": 50},
    },
    "required": ["query"],
}


# ---------------------------------------------------------------------------
# file_info
# ---------------------------------------------------------------------------
async def file_info(path: str) -> str:
    """
    Return metadata about a workspace file: size, mtime, lines, MIME, sha256.

    Args:
        path: Workspace-relative file path.

    Returns:
        A Markdown report.
    """
    if not path:
        return "**Error.** `path` is required."
    try:
        target = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not target.exists():
        return f"**Not found:** `{path}`"
    if target.is_dir():
        return f"`{path}` is a directory — use `list_directory` instead."

    st = target.stat()
    mime, _ = mimetypes.guess_type(str(target))
    sha = hashlib.sha256(target.read_bytes()).hexdigest()

    lines = None
    if st.st_size <= MAX_FILE_SIZE:
        try:
            with target.open("r", encoding="utf-8", errors="replace") as fh:
                lines = sum(1 for _ in fh)
        except OSError:
            lines = None

    rows = [
        ("Path", f"`{path}`"),
        ("Size", _human_size(st.st_size)),
        ("Modified", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))),
        ("MIME", mime or "unknown"),
    ]
    if lines is not None:
        rows.append(("Lines", str(lines)))
    rows.append(("SHA-256", f"`{sha[:16]}…{sha[-8:]}`"))

    body = "\n".join(f"| {k} | {v} |" for k, v in rows)
    return f"# File info\n\n| Field | Value |\n|---|---|\n{body}"


FILE_INFO_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "Workspace-relative file path."}},
    "required": ["path"],
}


# ---------------------------------------------------------------------------
# project_scaffold
# ---------------------------------------------------------------------------
_SCAFFOLDS: Dict[str, Dict[str, str]] = {
    "static": {
        "index.html": "<!doctype html>\n<html>\n<head>\n  <meta charset='utf-8'>\n  <meta name='viewport' content='width=device-width'>\n  <title>{name}</title>\n  <link rel='stylesheet' href='style.css'>\n</head>\n<body>\n  <h1>{name}</h1>\n  <p>Edit <code>index.html</code> to get started.</p>\n  <script src='app.js'></script>\n</body>\n</html>\n",
        "style.css": "* { box-sizing: border-box; margin: 0; }\nbody { font-family: system-ui; padding: 2rem; line-height: 1.6; }\n",
        "app.js": "console.log('Hello from {name}!');\n",
        "README.md": "# {name}\n\nA static site scaffolded by Nexa Agent.\n",
    },
    "next": {
        "package.json": '{\n  "name": "{slug}",\n  "private": true,\n  "scripts": {\n    "dev": "next dev",\n    "build": "next build",\n    "start": "next start"\n  },\n  "dependencies": {\n    "next": "latest",\n    "react": "latest",\n    "react-dom": "latest"\n  }\n}\n',
        "app/layout.tsx": "export const metadata = { title: '{name}' };\n\nexport default function RootLayout({\n  children,\n}: {\n  children: React.ReactNode;\n}) {\n  return (\n    <html lang=\"en\">\n      <body>{children}</body>\n    </html>\n  );\n}\n",
        "app/page.tsx": "export default function Page() {\n  return (\n    <main style={{ padding: '2rem', fontFamily: 'system-ui' }}>\n      <h1>{name}</h1>\n      <p>Edit <code>app/page.tsx</code> to get started.</p>\n    </main>\n  );\n}\n",
        "app/globals.css": "* { box-sizing: border-box; }\n",
        "next.config.ts": "import type { NextConfig } from 'next';\nconst config: NextConfig = {};\nexport default config;\n",
        "tsconfig.json": '{\n  "compilerOptions": {\n    "target": "ES2017",\n    "lib": ["dom", "dom.iterable", "esnext"],\n    "allowJs": true,\n    "skipLibCheck": true,\n    "strict": true,\n    "noEmit": true,\n    "esModuleInterop": true,\n    "module": "esnext",\n    "moduleResolution": "bundler",\n    "resolveJsonModule": true,\n    "isolatedModules": true,\n    "jsx": "preserve",\n    "incremental": true,\n    "plugins": [{ "name": "next" }]\n  },\n  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],\n  "exclude": ["node_modules"]\n}\n',
        ".gitignore": "node_modules/\n.next/\nout/\n*.log\n.env.local\n",
        "README.md": "# {name}\n\nNext.js app scaffolded by Nexa Agent.\n\n```\nnpm install\nnpm run dev\n```\n",
    },
    "vite-react": {
        "package.json": '{\n  "name": "{slug}",\n  "private": true,\n  "type": "module",\n  "scripts": {\n    "dev": "vite",\n    "build": "vite build",\n    "preview": "vite preview"\n  },\n  "dependencies": {\n    "react": "latest",\n    "react-dom": "latest"\n  },\n  "devDependencies": {\n    "@vitejs/plugin-react": "latest",\n    "vite": "latest"\n  }\n}\n',
        "index.html": "<!doctype html>\n<html>\n<head><meta charset='utf-8'><title>{name}</title></head>\n<body><div id='root'></div>\n<script type='module' src='/src/main.tsx'></script></body>\n</html>\n",
        "src/main.tsx": "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App';\n\ncreateRoot(document.getElementById('root')!).render(\n  <React.StrictMode><App /></React.StrictMode>\n);\n",
        "src/App.tsx": "export default function App() {\n  return (\n    <main style={{ padding: '2rem', fontFamily: 'system-ui' }}>\n      <h1>{name}</h1>\n    </main>\n  );\n}\n",
        "vite.config.ts": "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\n\nexport default defineConfig({ plugins: [react()] });\n",
        "tsconfig.json": '{ "compilerOptions": { "jsx": "react-jsx", "strict": true } }\n',
        ".gitignore": "node_modules/\ndist/\n*.log\n",
    },
    "express": {
        "package.json": '{\n  "name": "{slug}",\n  "private": true,\n  "type": "module",\n  "scripts": { "start": "node src/index.js", "dev": "node --watch src/index.js" }\n}\n',
        "src/index.js": "import express from 'express';\n\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.use(express.json());\napp.get('/', (_req, res) => res.json({ hello: '{name}' }));\napp.get('/health', (_req, res) => res.json({ ok: true }));\n\napp.listen(PORT, () => console.log(`{name} listening on http://localhost:${PORT}`));\n",
        ".gitignore": "node_modules/\n*.log\n.env\n",
        "README.md": "# {name}\n\n```\nnpm install express\nnpm run dev\n```\n",
    },
    "fastapi": {
        "requirements.txt": "fastapi\nuvicorn[standard]\npydantic\n",
        "src/main.py": "\"\"\"{name} — FastAPI app scaffolded by Nexa Agent.\"\"\"\nfrom fastapi import FastAPI\n\napp = FastAPI(title=\"{name}\")\n\n\n@app.get(\"/\")\ndef root() -> dict:\n    return {\"hello\": \"{name}\"}\n\n\n@app.get(\"/health\")\ndef health() -> dict:\n    return {\"ok\": True}\n",
        ".gitignore": "__pycache__/\n*.pyc\n.venv/\n.env\n",
        "README.md": "# {name}\n\n```\npip install -r requirements.txt\nuvicorn src.main:app --reload\n```\n",
    },
    "python-cli": {
        "requirements.txt": "typer\nrich\n",
        "src/main.py": "\"\"\"{name} — Python CLI scaffolded by Nexa Agent.\"\"\"\nimport typer\nfrom rich import print\n\napp = typer.Typer(help=\"{name}\")\n\n\n@app.command()\ndef hello(name: str = \"world\") -> None:\n    \"\"\"Say hello.\"\"\"\n    print(f\"[bold green]Hello, {name}![/bold green]\")\n\n\nif __name__ == \"__main__\":\n    app()\n",
        "README.md": "# {name}\n\n```\npip install -r requirements.txt\npython -m src.main hello\n```\n",
    },
    "empty": {},
}


def _slugify(name: str) -> str:
    """Make a package-friendly slug from a display name."""
    import re as _re
    s = name.lower()
    s = _re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "app"


async def project_scaffold(project_name: str, kind: str = "next", path: str = "") -> str:
    """
    Generate a starter project inside the workspace.

    Supported kinds: ``static``, ``next``, ``vite-react``, ``express``,
    ``fastapi``, ``python-cli``, ``empty``.

    Args:
        project_name: Display name (used in titles/READMEs).
        kind:         One of the scaffold kinds above.
        path:         Workspace subdirectory to create the project in.
                      Defaults to ``./<slugified-name>/``.

    Returns:
        A report of files created.
    """
    kind = (kind or "").lower()
    if kind not in _SCAFFOLDS:
        return (
            f"**Error.** Unknown scaffold kind `{kind}`. "
            f"Try one of: {', '.join(sorted(_SCAFFOLDS))}."
        )

    slug = _slugify(project_name)
    base_rel = path.strip() or slug
    try:
        root = resolve_in_workspace(base_rel)
    except ValueError as exc:
        return f"**Error.** {exc}"
    root.mkdir(parents=True, exist_ok=True)

    files = _SCAFFOLDS[kind]
    created: List[str] = []
    for rel, template in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Use %s substitution — safer than .format() for templates that
        # contain JSON braces (package.json, tsconfig.json).
        content = template.replace("{name}", project_name).replace("{slug}", slug)
        target.write_text(content, encoding="utf-8")
        created.append(rel)

    next_cmd = {
        "static": f"open `{base_rel}/index.html` in the Web Preview",
        "next": f"`cd {base_rel} && npm install && npm run dev`",
        "vite-react": f"`cd {base_rel} && npm install && npm run dev`",
        "express": f"`cd {base_rel} && npm install express && npm run dev`",
        "fastapi": f"`cd {base_rel} && pip install -r requirements.txt && uvicorn src.main:app --reload`",
        "python-cli": f"`cd {base_rel} && pip install -r requirements.txt && python -m src.main hello`",
        "empty": "nothing to run",
    }[kind]

    report = [
        f"# Scaffolded `{kind}`: {project_name}",
        "",
        f"Created **{len(created)}** file(s) in `{base_rel}/`:",
        "",
    ]
    report += [f"- `{rel}`" for rel in created]
    report += ["", "**Next:** " + next_cmd]
    return "\n".join(report)


PROJECT_SCAFFOLD_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_name": {"type": "string", "description": "Display name of the project."},
        "kind": {
            "type": "string",
            "enum": sorted(_SCAFFOLDS.keys()),
            "description": "Scaffold type.",
            "default": "next",
        },
        "path": {"type": "string", "description": "Optional workspace subdirectory."},
    },
    "required": ["project_name"],
}
