# OpenForge — Unified installer for Windows (PowerShell)
# ======================================================
#
# One-line install (run in PowerShell — NOT Command Prompt):
#   irm https://raw.githubusercontent.com/neuralforgeio/openforge/main/scripts/install/install.ps1 | iex
#
# Target layout:
#   ~/.openforge/
#   ├── lib/          (code — read-only where possible)
#   ├── .venv/        (virtualenv)
#   ├── workspace/    (your files)
#   ├── memory/  secrets/  sessions/  logs/  tools/  extensions/
#   └── openforge.db
#
# Copyright (c) 2026 Dearly Febriano Irwansyah
# SPDX-License-Identifier: MIT
#

param(
  [string]$Branch = "main",
  [string]$ForgeHome = $(if ($env:FORGE_HOME) { $env:FORGE_HOME } else { Join-Path $HOME ".openforge" }),
  [string]$RepoUrl = "https://github.com/neuralforgeio/openforge.git"
)

$ErrorActionPreference = "Stop"
$ForgeLib = Join-Path $ForgeHome "lib"
$VenvDir  = Join-Path $ForgeHome ".venv"
$VenvPy   = Join-Path $VenvDir  "Scripts\python.exe"

function Write-Step([string]$msg) { Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "  ✗ $msg" -ForegroundColor Red; exit 1 }

Write-Host ("`n=== OpenForge installer === " + (Get-Date)) -ForegroundColor White
Write-Step "Sanity checks"
foreach ($cmd in @("git", "python", "uv", "npm")) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) { Write-Ok "$cmd present" } else { Write-Warn "$cmd not found — continuing (install if missing)" }
}

Write-Step "Create unified layout ($ForgeHome)"
$dirs = @("memory","secrets","sessions","logs","tools","extensions","workspace",".permissions",".versions",".backups","lib")
foreach ($d in $dirs) { New-Item -ItemType Directory -Force (Join-Path $ForgeHome $d) | Out-Null }
# tighten secrets dir ACL (best-effort)
try { (Get-Item (Join-Path $ForgeHome "secrets")).Attributes = "Hidden" } catch {}
Write-Ok "folders ready"

Write-Step "Clone OpenForge → $ForgeLib"
if (Test-Path (Join-Path $ForgeLib ".git")) {
  Write-Host "  lib/ exists — pulling latest..." -ForegroundColor DarkGray
  Push-Location $ForgeLib; git pull --ff-only origin $Branch 2>$null; Pop-Location
} else {
  git clone --depth 1 -b $Branch $RepoUrl $ForgeLib
}
Write-Ok "code ready in $ForgeLib"

Write-Step "Create virtualenv"
if (-not (Test-Path $VenvPy)) { uv venv --python (Get-Command python).Source $VenvDir | Out-Null }
Write-Ok "venv at $VenvDir"

Write-Step "Install OpenForge package"
Push-Location $ForgeLib
$env:VIRTUAL_ENV = $VenvDir
$env:PATH = "$VenvDir\Scripts;$env:PATH"
try { uv pip install --python $VenvPy -e "." | Out-Null } catch { & $VenvPy -m pip install -e "." | Out-Null }
Pop-Location
Write-Ok "dependencies installed"

Write-Step "Frontend dependencies (openforge_web)"
$webDir = Join-Path $ForgeLib "openforge_web"
if (Test-Path $webDir) {
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location $webDir
    npm install --no-audit --no-fund 2>&1 | Out-Null
    Pop-Location
    Write-Ok "openforge_web deps installed"
  } else {
    Write-Warn "npm not found — skipping frontend deps. Later: cd $webDir && npm install"
  }
}

Write-Step "Finalize: permissions, LOCK, PATH shim"
# Mark lib read-only (best-effort on Windows)
try { (Get-ChildItem $ForgeLib -Recurse -File | ForEach-Object { $_.IsReadOnly = $true }) } catch {}
# Generate LOCK via the installed package
try {
  $env:FORGE_LIB = $ForgeLib
  & $VenvPy -c "from openforge.integrity import write_lock; import pathlib,os; write_lock(pathlib.Path(os.environ['FORGE_LIB']))" | Out-Null
  Write-Ok "LOCK written: $ForgeLib\LOCK"
} catch { Write-Warn "LOCK generate skipped: $_" }

# Add lib .venv Scripts to user PATH so openforge / openforge-chat work in any new shell.
$userPath = [Environment]::GetEnvironmentVariable("Path","User")
$bindir = Join-Path $VenvDir "Scripts"
if ($userPath -notlike "*$bindir*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$bindir","User")
  Write-Ok "PATH += $bindir (open a new shell to pick it up)"
} else {
  Write-Ok "PATH already contains $bindir"
}

# Initialize the FORGE_HOME structure.
write-Step "Initialize $ForgeHome"
try {
  & "$VenvDir\Scripts\openforge.exe" setup 2>&1 | Out-Null
  Write-Ok "OpenForge initialized (via openforge.exe)"
} catch {
  try { & $VenvPy -m openforge_cli setup 2>&1 | Out-Null; Write-Ok "OpenForge initialized (via python -m openforge_cli)" } catch {
    Write-Warn "openforge setup not available yet — run it manually later: openforge setup"
  }
}

Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "OpenForge is installed under: $ForgeLib" -ForegroundColor Green
Write-Host "Next: open a new PowerShell window, then run:" -ForegroundColor Cyan
Write-Host "  openforge --version`n  openforge setup`n  openforge doctor`n  openforge-chat" -ForegroundColor Yellow
