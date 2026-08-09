"""One-off: normalize in-tree version labels from v3.x / v4.0 → v4.1.0.

Strategy: SKIP files that document historical releases (CHANGELOG, worklog,
release notes, .plans/old-launch docs) so past releases stay accurate.
For everything in the actual source tree (py/./tools/.../forge_web/), replace
vMAJOR.MINOR.PATCH markers with v4.1.0 and bare "version = '4.X.Y'" with 4.1.0.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# Skip: historical release docs where old versions are facts, not current state.
SKIP_PATHS = {
    "worklog.md",
    "tests/REAL_INTEGRATION_REPORT.md",
    ".plans/release_body.json",
    ".plans/v3_launch_plan.md",
    ".plans/TASK_v4_PUNCHLIST.md",  # punchlist kept as historical task list
    ".plans/TODO_MASTER.md",
    ".plans/RESEARCH_UI_SANDBOX.md",
    ".plans/PLANNING_TOOLS_20.md",
    ".plans/FILE_ORGANIZATION.md",
    ".plans/STATE.json",
}
SKIP_DIR_PARTS = {".git", "node_modules", ".next", ".venv", "__pycache__", "dist"}

# Patterns:  vN.N.N or N.N.N in explicit version slots
RE_V = re.compile(r"\bv[34]\.[0-9]+\.[0-9]+\b")
RE_VERSION_EQ = re.compile(r'(\bversion\s*=\s*["\'])3\.[0-9]+\.[0-9]+(["\'])')
RE_VERSION_JSON = re.compile(r'("version"\s*:\s*")3\.[0-9]+\.[0-9]+(")')

REPORT = []

def should_skip(p: Path) -> bool:
    if p in SKIP_PATHS or p.name in SKIP_PATHS:
        return True
    parts = set(p.parts)
    if parts & SKIP_DIR_PARTS:
        return True
    return False

def clean_text(text: str, path: Path) -> tuple[str, int]:
    changes = 0
    def sub_v(m):
        nonlocal changes
        changes += 1
        return "v4.1.0"
    text = RE_V.sub(sub_v, text)
    text, n2 = RE_VERSION_EQ.subn(r"\g<1>4.1.0\g<2>", text)
    changes += n2
    text, n3 = RE_VERSION_JSON.subn(r"\g<1>4.1.0\g<2>", text)
    changes += n3
    return text, changes

def main() -> int:
    exts = (".py", ".ts", ".tsx", ".toml", ".json", ".md", ".ps1", ".sh", ".txt", ".css")
    files_changed = 0
    total_subs = 0

    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in exts:
            continue
        rel = p.relative_to(ROOT)
        if should_skip(rel):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except Exception:
            continue
        new_text, n = clean_text(text, rel)
        if n and new_text != text:
            p.write_text(new_text, encoding="utf-8", newline="")
            files_changed += 1
            total_subs += n
            REPORT.append(f"  {rel}: {n} substs")

    print(f"Changed {files_changed} files / {total_subs} substitutions")
    for line in REPORT[:80]:
        print(line)
    return 0

if __name__ == "__main__":
    sys.exit(main())
