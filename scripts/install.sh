#!/usr/bin/env bash
#
# Nexa Agent — Installer for Linux & macOS
# ==========================================
#
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh | bash
#
# Or with wget:
#   wget -qO- https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh | bash
#
# This script:
#   1. Checks for Python 3.11+ (installs via system package manager if missing).
#   2. Installs `uv` (Astral's fast Python package manager).
#   3. Clones nexa-agent to ~/nexa-agent (or a custom location).
#   4. Creates a virtual environment via uv.
#   5. Installs all Python dependencies.
#   6. Runs `nexa setup` to initialize ~/.nexa/.
#   7. Prints next steps.
#
# Copyright (c) 2026 Dearly Febriano Irwansyah
# SPDX-License-Identifier: MIT
#

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[nexa]${NC} $*"; }
ok()    { echo -e "${GREEN}[nexa] ✓${NC} $*"; }
warn()  { echo -e "${YELLOW}[nexa] ⚠${NC} $*"; }
fail()  { echo -e "${RED}[nexa] ✗${NC} $*"; exit 1; }

# --- Config ---
REPO_URL="https://github.com/neuralforgeio/nexa-agent.git"
INSTALL_DIR="${NEXA_INSTALL_DIR:-$HOME/nexa-agent}"
BRANCH="main"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Nexa Agent — Installer (Linux/macOS)   ║${NC}"
echo -e "${CYAN}║   by Dearly Febriano Irwansyah           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# --- Step 1: Check / install Python ---
info "Step 1/6: Checking Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+..."

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PY_VERSION=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [ "$PY_MAJOR" -gt "$PYTHON_MIN_MAJOR" ] || { [ "$PY_MAJOR" -eq "$PYTHON_MIN_MAJOR" ] && [ "$PY_MINOR" -ge "$PYTHON_MIN_MINOR" ]; }; then
            PYTHON_BIN="$candidate"
            ok "Found $candidate v$PY_VERSION"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    warn "Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv
        PYTHON_BIN="python3"
    elif command -v brew &>/dev/null; then
        brew install python@3.12
        PYTHON_BIN="python3"
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip
        PYTHON_BIN="python3"
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3
        PYTHON_BIN="python3"
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python
        PYTHON_BIN="python3"
    else
        fail "Could not auto-install Python. Please install Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ manually from https://python.org and re-run this script."
    fi
    ok "Python installed: $PYTHON_BIN"
fi

# --- Step 2: Install uv ---
info "Step 2/6: Checking uv (fast Python package manager)..."
if command -v uv &>/dev/null; then
    ok "uv already installed: $(uv --version)"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if command -v uv &>/dev/null; then
        ok "uv installed: $(uv --version)"
    else
        fail "uv installation failed. Install manually: https://docs.astral.sh/uv/"
    fi
fi

# --- Step 3: Clone or update the repo ---
info "Step 3/6: Cloning nexa-agent to $INSTALL_DIR..."
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Directory exists — pulling latest..."
    cd "$INSTALL_DIR"
    git pull --ff-only origin "$BRANCH" || warn "git pull failed (continuing with existing code)"
else
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
ok "Repository ready at $INSTALL_DIR"

# --- Step 4: Create virtual environment via uv ---
info "Step 4/6: Creating virtual environment..."
if [ ! -d ".venv" ]; then
    uv venv --python "$PYTHON_BIN"
    ok "Virtual environment created (.venv)"
else
    ok "Virtual environment already exists (.venv)"
fi

# --- Step 5: Install dependencies ---
info "Step 5/6: Installing Python dependencies (this may take a minute)..."
uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e . || pip install -e .
ok "Dependencies installed"

# --- Step 6: Run nexa setup ---
info "Step 6/6: Initializing ~/.nexa/..."
# Activate venv for the setup command.
export PATH="$INSTALL_DIR/.venv/bin:$PATH"
nexa setup 2>/dev/null || python -m nexa_cli setup 2>/dev/null || warn "nexa setup not yet available (install entry points first)"
ok "Nexa Agent initialized"

# --- Done ---
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ Nexa Agent installed successfully!   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Quick start:${NC}"
echo ""
echo "  1. Configure a provider (interactive — will prompt for API key):"
echo "     ${GREEN}nexa provider add tokenrouter${NC}"
echo ""
echo "  2. Start chatting (interactive REPL):"
echo "     ${GREEN}nexa-chat${NC}"
echo ""
echo "  3. Or start the Web UI (backend + frontend):"
echo "     ${GREEN}nexa gateway start${NC}    # backend on port 8000"
echo "     ${GREEN}cd $INSTALL_DIR/nexa_web && npm install && npm run dev${NC}  # frontend on port 3000"
echo ""
echo -e "${CYAN}Installed at:${NC} $INSTALL_DIR"
echo -e "${CYAN}Nexa home:${NC}    $HOME/.nexa/"
echo -e "${CYAN}Docs:${NC}         https://github.com/neuralforgeio/nexa-agent"
echo ""
echo -e "${YELLOW}Tip:${NC} Add $INSTALL_DIR/.venv/bin to your PATH for easy access:"
echo "  echo 'export PATH=\"$INSTALL_DIR/.venv/bin:\$PATH\"' >> ~/.bashrc"
echo ""
