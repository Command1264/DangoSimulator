$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonVersion = "3.12"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Windows Python Launcher 'py' is required. Install Python with launcher support, then rerun this script."
}

if (-not (Test-Path $VenvPath)) {
    py "-$PythonVersion" -m venv $VenvPath
}

$Python = Join-Path $VenvPath "Scripts\python.exe"
& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -e $ProjectRoot --no-deps
& $Python -m pip install -r (Join-Path $ProjectRoot "requirements-dev.txt")

Write-Host "Development environment ready: $Python"
