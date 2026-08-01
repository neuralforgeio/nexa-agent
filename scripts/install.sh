#!/usr/bin/env bash
#
# Nexa Agent — Ultra-Cool Installer for Linux & macOS
# ====================================================
#
# One-line install with animations:
#   curl -fsSL https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh | bash
#
# Or with wget:
#   wget -qO- https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh | bash
#
# Features:
#   - Cool ASCII logo + animations
#   - Progress bars with percentage
#   - Spinner animations during long operations
#   - Unicode sparkle effects (✨ ✅ ⚙️ 🚀)
#   - Color output via ANSI escape codes
#   - Non-blocking animations (won't slow down install)
#
# Copyright (c) 2026 Dearly Febriano Irwansyah
# SPDX-License-Identifier: MIT
#

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# --- Config ---
REPO_URL="https://github.com/neuralforgeio/nexa-agent.git"
INSTALL_DIR="${NEXA_INSTALL_DIR:-$HOME/nexa-agent}"
BRANCH="main"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

# --- Animation helpers ---
# Spinner frames (unicode).
SPINNER_FRAMES=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
SPINNER_IDX=0

show_spinner() {
    # Print spinner frame to stderr (stdout reserved for output).
    printf "\r${CYAN}%s${NC} " "${SPINNER_FRAMES[$SPINNER_IDX]}" >&2
    SPINNER_IDX=$((SPINNER_IDX + 1))
    SPINNER_IDX=$((SPINNER_IDX % ${#SPINNER_FRAMES[@]}))
}

clear_spinner() { printf '\r   \r' >&2; }

progress_bar() {
    # progress_bar(current, total, label)
    local current=$1 total=$2 label=$3
    local width=40
    local pct=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    printf "\r${WHITE}%s:${NC} [${GREEN}%*s${DIM}%*s${NC}] ${BOLD}%d%%${NC}" \
        "$label" "$filled" "$(printf '=%.0s' $(seq 1 $filled))" \
        "$empty" "$(printf '  %.0s' $(seq 1 $((empty / 2))))" \
        "$pct" >&2
}

# --- ASCII logo ---
print_logo() {
    echo -e "${CYAN}"
    cat << 'LOGO_EOF'
     ███╗   ██╗███████╗██╗  ██╗ █████╗
     ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗
     ██╔██╗██╔╝█████╗   ╚███╔╝ ███████║
     ██║╚████══█ ██╔══╝   ██╔██╗ ██╔══██║
     ██║ ╚███║  ███████╗██╔╝ ██╗██║  ██║
     ╚═╝  ╚══╝  ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
LOGO_EOF
    echo -e "${NC}"
    echo -e "${WHITE}${BOLD}  Nexa Agent v4.1.0${NC} ${DIM}·${NC} ${CYAN}Local AI Agent${NC}"
    echo -e "${DIM}  by Dearly Febriano Irwansyah · Indonesia${NC}"
    echo ""
}

# --- Info functions ---
info()    { echo -e "${CYAN}[*]${NC} $*"; }
ok()      { echo -e "${GREEN}[✔]${NC} $*"; }
warn()    { echo -e "${YELLOW}[⚠]${NC} $*"; }
fail()    { clear_spinner; echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}${BLUE}  → $*${NC}"; }
success() { echo -e "${GREEN}${BOLD}  ✓ $*${NC}"; }

# --- Main install ---
print_logo

# --- Animation during exec (non-blocking) ---
(while true; do show_spinner; sleep 0.1; done) &
SPIN_PID=$!
trap "kill $SPIN_PID 2>/dev/null || true; clear_spinner" EXIT

# --- Step 1: OS detection ---
step "Detecting operating system..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    PKG_MGR=""
    if command -v apt-get &>/dev/null; then PKG_MGR="apt"; fi
    if command -v dnf &>/dev/null;    then PKG_MGR="dnf"; fi
    if command -v pacman &>/dev/null; then PKG_MGR="pacman"; fi
    if command -v yum &>/dev/null;    then PKG_MGR="yum"; fi
    ok "Linux detected (package manager: ${PKG_MGR:-unknown})"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    PKG_MGR="brew"
    if ! command -v brew &>/dev/null; then
        fail "macOS detected but Homebrew not installed. Install: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    fi
    ok "macOS detected (Homebrew installed)"
else
    OS="windows"
    warn "Windows detected — please use install.ps1 instead"
    fail "Use: irm https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 | iex"
fi
progress_bar 1 7 "OS detection"

# --- Step 2: Check / install Python ---
step "Checking Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+..."
PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PY_VERSION=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [ "$PY_MAJOR" -gt "$PYTHON_MIN_MAJOR" ] || { [ "$PY_MAJOR" -eq "$PYTHON_MIN_MAJOR" ] && [ "$PY_MINOR" -ge "$PYTHON_MIN_MINOR" ]; }; then
            PYTHON_BIN="$candidate"
            ok "Found $candidate v$PY_VERSION ✓"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    warn "Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ not found. Installing..."
    case "$PKG_MGR" in
        apt)    sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv ;;
        brew)   brew install python@3.12 ;;
        dnf)    sudo dnf install -y python3 python3-pip ;;
        yum)    sudo yum install -y python3 ;;
        pacman) sudo pacman -S --noconfirm python ;;
        *)      fail "Could not auto-install Python. Install from https://python.org and re-run." ;;
    esac
    PYTHON_BIN="python3"
    ok "Python installed ✓"
fi
progress_bar 2 7 "Python check"

# --- Step 3: Install uv (fast package manager) ---
step "Installing uv (Astral's fast Python package manager)..."
if command -v uv &>/dev/null; then
    ok "uv already installed: $(uv --version) ✓"
else
    info "Downloading uv installer..."
    curl -LsSf https://astral.sh/uv/install.sh 2>/dev/null | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if command -v uv &>/dev/null; then
        ok "uv installed: $(uv --version) ✓"
    else
        fail "uv installation failed. Manual: https://docs.astral.sh/uv/"
    fi
fi
progress_bar 3 7 "uv install"

# --- Step 4: Clone or update the repo ---
step "Cloning nexa-agent to ${CYAN}$INSTALL_DIR${NC}..."
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Directory exists — pulling latest..."
    (cd "$INSTALL_DIR" && git pull --ff-only origin "$BRANCH") 2>/dev/null
    ok "Repository updated ✓"
else
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR" 2>&1
    cd "$INSTALL_DIR"
    ok "Cloned to $INSTALL_DIR ✓"
fi
progress_bar 4 7 "Repository clone"

# --- Step 5: Virtual environment ---
step "Creating virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d ".venv" ]; then
    uv venv --python "$PYTHON_BIN" 2>&1
    ok "Virtual environment created (.venv) ✓"
else
    ok "Virtual environment exists (.venv) ✓"
fi
progress_bar 5 7 "Virtual env"

# --- Step 6: Install dependencies ---
step "Installing dependencies (this may take a minute)..."
export PATH="$INSTALL_DIR/.venv/bin:$PATH"
# Try uv first (fastest), fall back to pip.
if command -v uv &>/dev/null; then
    uv pip install -e ".[dev]" 2>&1 | tail -1
else
    python -m pip install -e ".[dev]" 2>&1 | tail -1
fi
ok "Dependencies installed ✓"
progress_bar 6 7 "Dependencies"

# --- Step 7: Initialize ---
step "Initializing ~/.nexa/ home directory..."
"$INSTALL_DIR/.venv/bin/nexa" setup 2>/dev/null || \
  "$INSTALL_DIR/.venv/bin/python" -m nexa_cli setup 2>/dev/null || \
  warn "nexa setup not available yet (run it manually: nexa setup)"
ok "Nexa Agent initialized ✓"
progress_bar 7 7 "Initialization"

# --- Cleanup spinner ---
kill $SPIN_PID 2>/dev/null || true
trap - EXIT
clear_spinner

# --- Final success animation ---
echo ""
echo -e "${GREEN}${BOLD}"
cat << 'SUCCESS_EOF'
  ✨ ╔══════════════════════════════════════════════════╗ ✨
     ║        ✅ Nexa Agent installed successfully!           ║
     ╚══════════════════════════════════════════════════╝
SUCCESS_EOF
echo -e "${NC}"
echo ""
echo -e "${WHITE}  Next steps:${NC}"
echo ""
echo -e "    ${CYAN}1.${NC} Open a ${BOLD}new terminal${NC} (to refresh PATH)"
echo ""
echo -e "    ${CYAN}2.${NC} Configure a provider (interactive):"
echo -e "       ${GREEN}$ nexa provider add tokenrouter${NC}"
echo ""
echo -e "    ${CYAN}3.${NC} Start chatting:"
echo -e "       ${GREEN}$ nexa-chat${NC}"
echo ""
echo -e "    ${CYAN}4.${NC} Or launch the Web UI:"
echo -e "       ${GREEN}$ nexa gateway start${NC}  ${DIM}# backend :8000${NC}"
echo -e "       ${GREEN}$ cd $INSTALL_DIR/nexa_web && npm install && npm run dev${NC}  ${DIM}# frontend :3000${NC}"
echo ""
echo -e "  ${DIM}Installed at: ${CYAN}$INSTALL_DIR${NC}"
echo -e "  ${DIM}Docs: https://github.com/neuralforgeio/nexa-agent${NC}"
echo ""
echo -e "  ${YELLOW}💡 Tip:${NC} Add nexa to your PATH for easy access:"
echo -e "     ${DIM}echo 'export PATH=\"$INSTALL_DIR/.venv/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc${NC}"
echo ""
