"""Purge: eliminate every forge identifier across the repo (user mandate).

Ordered replacements (order matters):
  1. "OpenForge"  -> "OpenForge"
  2. "openforge"  -> "openforge"
  3. "openforge"  -> "openforge"
  4. "FORGE_"       -> "FORGE_"
  5. ".openforge"       -> ".openforge"
  6. "forge-workspace" -> "forge-workspace"
  7. \bnexa_\w+    -> forge_<word>   (identifiers like forge_home)
  8. \bopenforge\b      -> "forge"        (bare lowercase word)
  9. \bOpenForge\b      -> "Forge"        (bare capitalized word)

Skips: .git, .venv, node_modules, __pycache__, media/binary extensions.
This is a one-shot script; it deletes itself after running.
"""
import io
import os
import re
from pathlib import Path

ROOT = Path(r"C:\Users\Dearly Febriano\openforge")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".next", "dist", "build", "coverage"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".db", ".gz", ".woff", ".woff2", ".ttf", ".lock", ".uv", ".pyc"}

RULES = [
    (re.compile(r"OpenForge"), "OpenForge"),
    (re.compile(r"openforge"), "openforge"),
    (re.compile(r"openforge"), "openforge"),
    (re.compile(r"FORGE_"), "FORGE_"),
    (re.compile(r"\.openforge"), ".openforge"),
    (re.compile(r"forge-workspace"), "forge-workspace"),
    (re.compile(r"\bnexa_([a-z]+)"), r"forge_\1"),
    (re.compile(r"\bopenforge\b"), "forge"),
    (re.compile(r"\bOpenForge\b"), "Forge"),
]

changed = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        p = Path(dirpath) / fn
        if p.suffix.lower() in SKIP_EXT:
            continue
        try:
            text = io.open(p, encoding="utf-8").read()
        except Exception:
            continue
        orig = text
        for rx, rep in RULES:
            text = rx.sub(rep, text)
        if text != orig:
            io.open(p, "w", encoding="utf-8", newline="").write(text)
            changed += 1

print(f"sweep changed: {changed} files")

# Second pass: count residuals (should be ~0 outside .git internals).
left = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        p = Path(dirpath) / fn
        if p.suffix.lower() in SKIP_EXT:
            continue
        try:
            text = io.open(p, encoding="utf-8").read()
        except Exception:
            continue
        if re.search(r"forge|Forge|FORGE", text):
            left.append(str(p.relative_to(ROOT)))
print(f"residual files: {len(left)}")
for f in left[:40]:
    print("  LEFT:", f)
