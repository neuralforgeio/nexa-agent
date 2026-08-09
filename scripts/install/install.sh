#!/usr/bin/env bash
#
# OpenForge — Unified installer for Linux & macOS
# ===================================================
#
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/neuralforgeio/openforge/main/scripts/install/install.sh| bash
#
# Target layout (SINGLE ROOT — no scattered folders):
#   ~/.openforge/
#   ├── lib/           (code — read-only, chmod 555)
#   ├── .venv/         (virtualenv)
#   ├── workspace/     (RW: your files)
#   ├── memory/ secrets/ sessions/ logs/ tools/ extensions/
#   ├── .permissions/  .versions/  .backups/   (RW, dot-dirs)
#   └── openforge.db   (created on first `openforge setup`, not at install time)
#
# LOCK integrity is written to ~/.openforge/lib/LOCK before lib/ is made read-only.
#
# Copyright (c) 2026 Dearly Febriano Irwansyah
# SPDX-License-Identifier: MIT
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

REPO_URL="https://github.com/neuralforgeio/openforge.git"
BRANCH="main"
FORGE_HOME="${FORGE_HOME:-$HOME/.openforge}"
FORGE_LIB="$FORGE_HOME/lib"
VENV_DIR="$FORGE_HOME/.venv"

# --- Output helpers ---
ok()   { printf "${GREEN}✓${NC} %s\n" "$*"; }
info() { printf "${CYAN}i${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}⚠${NC} %s\n" "$*"; }
fail() { printf "${RED}✗${NC} %s\n" "$*" >&2; exit 1; }
step() { printf "\n${BOLD}[%s/%s]${NC} %s\n" "$1" "$2" "$3"; }

echo -e "${CYAN}${BOLD}"
cat << 'BANNER'
  ____                    ______                    _
 / __ \                  |  ____|                  | |
| |  | |_ __   ___ _ __  | |__ ___  _ __ __ _  ___| |
| |  | | '_ \ / _ \ '_ \ |  __/ _ \| '__/ _` |/ _ \ |
| |__| | |_) |  __/ | | || | | (_) | | | (_| |  __/_|
 \____/| .__/ \___|_| |_||_|  \___/|_|  \__, |\___(_)
       | |                                __/ |
       |_|                               |___/
BANNER
echo -e "${DIM}Forge intelligent code, locally.${NC}\n"

# ---- Sanity checks -----------------------------------------------------------
step 1 7 "Environment checks"
command -v git >/dev/null 2>&1 || fail "git not found. Install git first."
command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install Python 3.11+ first."
PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYM=$(python3 -c 'import sys; print(sys.version_info.major)')
PYm=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYM" -lt 3 ] || { [ "$PYM" -eq 3 ] && [ "$PYm" -lt 11 ]; }; then
    fail "Python >= 3.11 required (found $PYV)."
fi
ok "python $PYV"
step 2 7 "Install uv"
if ! command -v uv >/dev/null 2>&1; then
    info "uv not found; installing via official installer..."
    curl -fsSL https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || fail "uv install failed"
    export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv: $(uv --version)"

# ---- Create unified folder skeleton -----------------------------------------
step 3 7 "Create unified layout ($FORGE_HOME)"
mkdir -p "$FORGE_HOME"/{memory,secrets,sessions,logs,tools,extensions,workspace,.permissions,.versions,.backups}
chmod 700 "$FORGE_HOME/secrets" 2>/dev/null || true
# QA-G-9: also tighten any credential files to owner-only read/write.
find "$FORGE_HOME/secrets" -type f -exec chmod 600 {} + 2>/dev/null || true
ok "created ~/.openforge structure"

# ---- Clone code into lib/ ----------------------------------------------------
step 4 7 "Clone OpenForge → $FORGE_LIB"
if [ -d "$FORGE_LIB/.git" ]; then
    info "lib/ exists — updating..."
    (cd "$FORGE_LIB" && git pull --ff-only origin "$BRANCH") || warn "git pull failed (using existing)"
else
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$FORGE_LIB"
fi
ok "code ready in $FORGE_LIB"

# ---- Virtual environment -----------------------------------------------------
step 5 7 "Virtual environment"
if [ ! -d "$VENV_DIR" ]; then
    uv venv --python "$(command -v python3)" "$VENV_DIR"
fi
VENV_PY="$VENV_DIR/bin/python"
ok "venv: $VENV_DIR/bin/python"

# ---- Install dependencies -----------------------------------------------------
step 6 7 "Install OpenForge + deps"
(
  cd "$FORGE_LIB"
  unset VIRTUAL_ENV
  export VIRTUAL_ENV="$VENV_DIR"
  export PATH="$VENV_DIR/bin:$PATH"
  uv pip install --python "$VENV_PY" -e "." | tail -1
)
ok "packages installed"

# ---- Step 6b: Frontend dependencies -------------------------------------------
# Auto-install openforge_web deps when npm is available (graceful skip otherwise).
if [ -d "$FORGE_LIB/openforge_web" ]; then
    if command -v npm >/dev/null 2>&1; then
        step "6b" "Install frontend dependencies (openforge_web)..."
        if (cd "$FORGE_LIB/openforge_web" && npm install --no-audit --no-fund 2>&1 | tail -1); then
            ok "Frontend dependencies installed ✓"
        else
            warn "npm install failed — run manually: cd $FORGE_LIB/openforge_web && npm install"
        fi
    else
        info "npm not found — frontend deps skipped. Later: cd $FORGE_LIB/openforge_web && npm install"
    fi
fi

# ---- Bootstraps: LOCK + permissions ------------------------------------------
step 7 7 "Finalize: permissions, PATH, LOCK"

# QA-G-1 fix: write the LOCK manifest FIRST, then mark lib/ read-only.
FORGE_LIB="$FORGE_LIB" "$VENV_PY" - <<'PY2' || warn "integrity.LOCK generation skipped"
import os, sys
sys.path.insert(0, os.environ["FORGE_LIB"])
from openforge.integrity import write_lock
lock = write_lock(__import__("pathlib").Path(os.environ["FORGE_LIB"]))
print("LOCK written:", lock)
PY2

# Make lib/ read-only (protect the agent from rewriting itself) — AFTER LOCK.
chmod -R a-w "$FORGE_LIB" 2>/dev/null || warn "chmod -w on lib/ only partially applied"

# QA-G-2 fix: binaries live in the venv that the installer created at
# $FORGE_HOME/.venv (NOT $FORGE_LIB/.venv). Link from the correct location.
mkdir -p "$HOME/.local/bin"
for b in openforge openforge-chat openforge-agent openforge-tui; do
  if [ -x "$VENV_DIR/bin/$b" ]; then
    ln -sf "$VENV_DIR/bin/$b" "$HOME/.local/bin/$b"
  fi
done
ok "linked into ~/.local/bin"

# ---- Success banner -----------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}"
cat << 'DONE'
  ✨ ╔══════════════════════════════════════════════════╗ ✨
     ║        ✅ OpenForge installed successfully!         ║
     ╚══════════════════════════════════════════════════╝
DONE
echo -e "${NC}"
echo -e "  ${WHITE}Installed to:${NC}  $FORGE_LIB"
echo -e "  ${WHITE}Data home:${NC}    $FORGE_HOME"
echo ""
echo -e "  ${CYAN}Next steps:${NC}"
echo -e "    1. Open a new terminal (or run: source ~/.bashrc)"
echo -e "    2. ${BOLD}openforge --version${NC}   # verify the install"
echo -e "    3. ${BOLD}openforge setup${NC}        # initialize ~/.openforge/ (db, secrets)"
echo -e "    4. ${BOLD}openforge doctor${NC}       # verify LOCK + structure"
echo -e "    5. ${BOLD}openforge provider add tokenrouter${NC}"
echo -e "    6. ${BOLD}openforge-chat${NC}         # start chatting"
echo ""
