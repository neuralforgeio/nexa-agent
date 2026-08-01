#
# Nexa Agent — Ultra-Cool Installer for Windows (PowerShell)
# ===========================================================
#
# One-line install (run in PowerShell — NOT Command Prompt):
#   irm https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 | iex
#
# Or save and run:
#   iwr https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 -OutFile install.ps1
#   .\install.ps1
#
# Features:
#   - Cool ASCII logo + animations
#   - Progress bars with percentage
#   - Unicode sparkle effects (✨ ✅ ⚙️ 🚀)
#   - Color output via ANSI escape codes (PowerShell 7 recommended)
#   - Non-blocking animations (won't slow down install)
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

# --- Helper functions ---
function Write-Info($msg)  { Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[✔] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[⚠] $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "[✗] $msg" -ForegroundColor Red; exit 1 }
function Write-Step($msg)  { Write-Host "`n  → $msg" -ForegroundColor Blue }
function Write-Success($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }

# Spinner animation (runs in background).
$global:SpinnerRunning = $false
function Start-Spinner {
    if ($global:SpinnerRunning) { return }
    $global:SpinnerRunning = $true
    $global:SpinnerJob = Start-Job -ScriptBlock {
        $frames = @('⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏')
        $i = 0
        while ($true) {
            $f = $frames[$i % $frames.Length]
            [System.Console]::Write("`r $f ")
            Start-Sleep -Milliseconds 80
            $i++
        }
    }
}
function Stop-Spinner {
    $global:SpinnerRunning = $false
    if ($global:SpinnerJob) {
        Stop-Job $global:SpinnerJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $global:SpinnerJob -ErrorAction SilentlyContinue | Out-Null
    }
    [System.Console]::Write("`r     `r")
}

function Write-ProgressBar {
    param([int]$current, [int]$total, [string]$label)
    $width = 40
    $pct = [int]($current * 100 / $total)
    $filled = [int]($current * $width / $total)
    $empty = $width - $filled
    $bar = "=" * $filled + " " * $empty
    Write-Host "`r ${label}: [$bar] ${pct}%" -NoNewline -ForegroundColor White
}

# --- ASCII logo ---
Write-Host ""
Write-Host "     ███╗   ██╗███████╗██╗  ██╗ █████╗" -ForegroundColor Cyan
Write-Host "     ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗" -ForegroundColor Cyan
Write-Host "     ██╔██╗██╔╝█████╗   ╚███╔╝ ███████║" -ForegroundColor Cyan
Write-Host "     ██║╚████══█ ██╔══╝   ██╔██╗ ██╔══██║" -ForegroundColor Cyan
Write-Host "     ██║ ╚███║  ███████╗██╔╝ ██╗██║  ██║" -ForegroundColor Cyan
Write-Host "     ╚═╝  ╚══╝  ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Nexa Agent v4.1.0  ·  Local AI Agent" -ForegroundColor White
Write-Host "  by Dearly Febriano Irwansyah · Indonesia" -ForegroundColor DarkGray
Write-Host ""

# --- Step 0: Git check ---
Write-Step "Checking git..."
$gitOK = $false
try { git --version | Out-Null; $gitOK = $true; Write-Ok "git found" } catch {}
if (-not $gitOK) {
    Write-Warn "git not found. Installing via winget..."
    try { winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements } catch {
        Write-Fail "Could not install git. Install from https://git-scm.com and re-run."
    }
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    git --version | Out-Null
    Write-Ok "git installed"
}
Write-ProgressBar 1 7 "Git check"

# --- Step 1: Python check / install ---
Write-Step "Checking Python 3.11+..."
$pythonBin = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
        if ($ver -match '^\d+\.\d+$') {
            $parts = $ver.Split('.')
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
                $pythonBin = $candidate
                Write-Ok "Found $candidate v$ver ✓"
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
        Write-Ok "Python installed ✓"
    } catch {
        Write-Fail "Could not install Python. Download from https://python.org and re-run."
    }
}
Write-ProgressBar 2 7 "Python check"

# --- Step 2: Install uv ---
Write-Step "Installing uv (Astral's fast Python package manager)..."
$uvOK = $false
try { uv --version | Out-Null; $uvOK = $true; Write-Ok "uv already installed ✓" } catch {}
if (-not $uvOK) {
    Write-Info "Downloading uv installer..."
    try {
        irm https://astral.sh/uv/install.ps1 | iex
        $env:Path = "$HOME\.local\bin;$env:Path"
        uv --version | Out-Null
        Write-Ok "uv installed ✓"
    } catch {
        Write-Warn "uv install failed. Trying pip..."
        & $pythonBin -m pip install uv 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Fail "Could not install uv." }
        Write-Ok "uv installed via pip ✓"
    }
}
Write-ProgressBar 3 7 "uv install"

# --- Step 3: Clone / update repo ---
Write-Step "Cloning nexa-agent to $InstallDir..."
if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Info "Directory exists — pulling latest..."
    try { (Set-Location $InstallDir) && (git pull --ff-only origin $Branch) 2>&1 | Out-Null; Write-Ok "Repository updated ✓" } catch {
        Write-Warn "git pull failed (continuing with existing code)"
    }
} else {
    git clone --depth 1 -b $Branch $RepoUrl $InstallDir 2>&1 | Out-Null
    Set-Location $InstallDir
    Write-Ok "Cloned to $InstallDir ✓"
}
Write-ProgressBar 4 7 "Repository clone"

# --- Step 4: Virtual environment ---
Write-Step "Creating virtual environment..."
$venvPath = Join-Path $InstallDir ".venv"
if (-not (Test-Path $venvPath)) {
    uv venv --python $pythonBin 2>&1 | Out-Null
    Write-Ok "Virtual environment created (.venv) ✓"
} else {
    Write-Ok "Virtual environment exists (.venv) ✓"
}
Write-ProgressBar 5 7 "Virtual env"

# --- Step 5: Install dependencies ---
Write-Step "Installing dependencies..."
Set-Location $InstallDir
$venvPython = Join-Path $venvPath "Scripts\python.exe"
try {
    uv pip install -e ".[dev]" 2>&1 | Out-Null
    Write-Ok "Dependencies installed ✓"
} catch {
    & $venvPython -m pip install -e ".[dev]" 2>&1 | Out-Null
    Write-Ok "Dependencies installed ✓"
}
Write-ProgressBar 6 7 "Dependencies"

# --- Step 6: Initialize ---
Write-Step "Initializing ~/.nexa/ home directory..."
try {
    & "$venvPath\Scripts\nexa.exe" setup 2>&1 | Out-Null
    Write-Ok "Nexa Agent initialized ✓"
} catch {
    try {
        & $venvPython -m nexa_cli setup 2>&1 | Out-Null
        Write-Ok "Nexa Agent initialized ✓"
    } catch {
        Write-Warn "nexa setup not available yet (run it manually: nexa setup)"
    }
}
Write-ProgressBar 7 7 "Initialization"

# --- Final success ---
Write-Host ""
Write-Host "  ✨ ╔══════════════════════════════════════════════════╗ ✨" -ForegroundColor Green
Write-Host "     ║        ✅ Nexa Agent installed successfully!           ║" -ForegroundColor Green
Write-Host "     ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "    1. Open a NEW PowerShell window (to refresh PATH):" -ForegroundColor Cyan
Write-Host ""
Write-Host "    2. Configure a provider:" -ForegroundColor Cyan
Write-Host "       $ nexa provider add tokenrouter" -ForegroundColor Green
Write-Host ""
Write-Host "    3. Start chatting:" -ForegroundColor Cyan
Write-Host "       $ nexa-chat" -ForegroundColor Green
Write-Host ""
Write-Host "    4. Or launch the Web UI:" -ForegroundColor Cyan
Write-Host "       $ nexa gateway start" -ForegroundColor Green
Write-Host "       $ cd $InstallDir\nexa_web && npm install && npm run dev" -ForegroundColor Green
Write-Host ""
Write-Host "  Installed at: $InstallDir" -ForegroundColor DarkGray
Write-Host "  Docs: https://github.com/neuralforgeio/nexa-agent" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  💡 Tip: Add nexa to your PATH:" -ForegroundColor Yellow
Write-Host "     `$env:Path += `";$InstallDir\.venv\Scripts`"" -ForegroundColor DarkGray
Write-Host ""
