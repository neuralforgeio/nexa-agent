#
# Nexa Agent — Installer for Windows (PowerShell)
# ===============================================
#
# One-line install (run in PowerShell):
#   irm https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 | iex
#
# Or save and run:
#   iwr https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 -OutFile install.ps1
#   .\install.ps1
#
# This script:
#   1. Checks for Python 3.11+ (downloads from python.org if missing).
#   2. Installs `uv` (Astral's fast Python package manager).
#   3. Clones nexa-agent to a user-chosen directory (default: $HOME\nexa-agent).
#   4. Creates a virtual environment via uv.
#   5. Installs all Python dependencies.
#   6. Runs `nexa setup` to initialize ~/.nexa/.
#   7. Prints next steps.
#
# Copyright (c) 2026 Dearly Febriano Irwansyah
# SPDX-License-Identifier: MIT
#

# Force TLS 1.2 for older Windows versions.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ErrorActionPreference = "Stop"

# --- Config ---
$RepoUrl = "https://github.com/neuralforgeio/nexa-agent.git"
$InstallDir = if ($env:NEXA_INSTALL_DIR) { $env:NEXA_INSTALL_DIR } else { Join-Path $HOME "nexa-agent" }
$Branch = "main"

function Write-Info($msg)  { Write-Host "[nexa] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[nexa] ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[nexa] ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "[nexa] ✗ $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Nexa Agent — Installer (Windows)       ║" -ForegroundColor Cyan
Write-Host "║   by Dearly Febriano Irwansyah           ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# --- Check for git ---
Write-Info "Step 0/6: Checking git..."
$gitInstalled = $false
try { $null = git --version; $gitInstalled = $true; Write-Ok "git found" } catch {}
if (-not $gitInstalled) {
    Write-Warn "git not found. Installing via winget..."
    try { winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements } catch {
        Write-Fail "Could not install git. Install from https://git-scm.com and re-run."
    }
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $null = git --version
    Write-Ok "git installed"
}

# --- Step 1: Check / install Python ---
Write-Info "Step 1/6: Checking Python 3.11+..."
$pythonBin = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $pyVer = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($pyVer) {
            $parts = $pyVer.Split('.')
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
                $pythonBin = $candidate
                Write-Ok "Found $candidate v$pyVer"
                break
            }
        }
    } catch {}
}
if (-not $pythonBin) {
    Write-Warn "Python 3.11+ not found. Installing via winget..."
    try {
        winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $pythonBin = "python"
        Write-Ok "Python installed"
    } catch {
        Write-Fail "Could not install Python. Download from https://python.org and re-run."
    }
}

# --- Step 2: Install uv ---
Write-Info "Step 2/6: Checking uv (fast Python package manager)..."
$uvInstalled = $false
try { $null = uv --version; $uvInstalled = $true; Write-Ok "uv found" } catch {}
if (-not $uvInstalled) {
    Write-Info "Installing uv..."
    try {
        irm https://astral.sh/uv/install.ps1 | iex
        $uvPath = Join-Path $HOME ".local\bin"
        $env:Path = "$uvPath;$env:Path"
        $null = uv --version
        Write-Ok "uv installed"
    } catch {
        Write-Warn "uv install via script failed. Trying pip..."
        & $pythonBin -m pip install uv
    }
}

# --- Step 3: Clone or update the repo ---
Write-Info "Step 3/6: Cloning nexa-agent to $InstallDir..."
if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Info "Directory exists — pulling latest..."
    Set-Location $InstallDir
    git pull --ff-only origin $Branch
    Write-Ok "Repository updated"
} else {
    git clone --depth 1 -b $Branch $RepoUrl $InstallDir
    Set-Location $InstallDir
    Write-Ok "Repository cloned"
}

# --- Step 4: Create virtual environment ---
Write-Info "Step 4/6: Creating virtual environment..."
$venvPath = Join-Path $InstallDir ".venv"
if (-not (Test-Path $venvPath)) {
    uv venv --python $pythonBin
    Write-Ok "Virtual environment created (.venv)"
} else {
    Write-Ok "Virtual environment already exists (.venv)"
}

# --- Step 5: Install dependencies ---
Write-Info "Step 5/6: Installing Python dependencies (this may take a minute)..."
try {
    uv pip install -e ".[dev]"
} catch {
    try { uv pip install -e . } catch { & $pythonBin -m pip install -e . }
}
Write-Ok "Dependencies installed"

# --- Step 6: Run nexa setup ---
Write-Info "Step 6/6: Initializing ~/.nexa/..."
$venvPython = Join-Path $venvPath "Scripts\python.exe"
try {
    & (Join-Path $venvPath "Scripts\nexa.exe") setup
    Write-Ok "Nexa Agent initialized"
} catch {
    try {
        & $venvPython -m nexa_cli setup
        Write-Ok "Nexa Agent initialized (via module)"
    } catch {
        Write-Warn "nexa setup not available yet (entry points may need reinstall)"
    }
}

# --- Done ---
Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   ✓ Nexa Agent installed successfully!   ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Quick start:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Open a NEW PowerShell window (to get the updated PATH)."
Write-Host ""
Write-Host "  2. Configure a provider (interactive — will prompt for API key):"
Write-Host "     nexa provider add tokenrouter" -ForegroundColor Green
Write-Host ""
Write-Host "  3. Start chatting (interactive REPL):"
Write-Host "     nexa-chat" -ForegroundColor Green
Write-Host ""
Write-Host "  4. Or start the Web UI (backend + frontend):"
Write-Host "     nexa gateway start      # backend on port 8000" -ForegroundColor Green
Write-Host "     cd $InstallDir\nexa_web" -ForegroundColor Green
Write-Host "     npm install; npm run dev   # frontend on port 3000" -ForegroundColor Green
Write-Host ""
Write-Host "Installed at: $InstallDir" -ForegroundColor Cyan
Write-Host "Nexa home:    $HOME\.nexa\" -ForegroundColor Cyan
Write-Host "Docs:         https://github.com/neuralforgeio/nexa-agent" -ForegroundColor Cyan
Write-Host ""
