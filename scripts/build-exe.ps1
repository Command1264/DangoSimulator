$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    & (Join-Path $PSScriptRoot "setup-dev.ps1")
}

& $Python -m pip install -r (Join-Path $ProjectRoot "requirements-gui.txt")
& $Python -m PyInstaller (Join-Path $ProjectRoot "DangoSimulator.spec") --noconfirm
