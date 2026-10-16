# One-step setup: right-click > Run with PowerShell, or `powershell -ExecutionPolicy Bypass -File install.ps1`.
# Installs into .venv here, adds Déjà to sign-in, and starts it. Nothing is installed system-wide.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = (Get-Command py, python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $py) { Write-Host "Install Python 3.11 or newer from python.org first, then run this again."; exit 1 }

if (-not (Test-Path .venv)) { & $py -m venv .venv }
.\.venv\Scripts\python -m pip install --quiet --upgrade pip
.\.venv\Scripts\python -m pip install --quiet -r requirements.txt
.\.venv\Scripts\python -m deja --install

if (Get-Command ollama -ErrorAction SilentlyContinue) { ollama pull gemma3:1b }
else { Write-Host "Optional: install Ollama from ollama.com and run 'ollama pull gemma3:1b' for one-line answers." }

Start-Process .\.venv\Scripts\pythonw.exe -ArgumentList "-m", "deja"
Write-Host "Déjà is running in the tray and will start at every sign-in. Remove that with: .venv\Scripts\python -m deja --uninstall"
