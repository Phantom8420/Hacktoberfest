# One-step setup: right-click > Run with PowerShell, or `powershell -ExecutionPolicy Bypass -File install.ps1`.
# Installs into .venv here, adds Déjà to sign-in, and starts it. Nothing is installed system-wide.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = (Get-Command py, python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if ($py) { & $py -c "import sys; sys.exit(sys.version_info < (3, 11))" }
if (-not $py -or $LASTEXITCODE) { Write-Host "Install Python 3.11 or newer from python.org first, then run this again."; exit 1 }

# Windows PowerShell does not stop when a program fails, so check each step
function Step($what) { if ($LASTEXITCODE) { Write-Host "Setup stopped: $what failed (see above)."; exit 1 } }
if (-not (Test-Path .venv)) { & $py -m venv .venv; Step "creating .venv" }
.\.venv\Scripts\python -m pip install --quiet --upgrade pip; Step "updating pip"
Write-Host "Installing Déjà's parts (about 300 MB the first time)..."
.\.venv\Scripts\python -m pip install --quiet -r requirements.txt; Step "installing requirements"
.\.venv\Scripts\python -m deja --install; Step "adding Déjà to sign-in"

if (Get-Command ollama -ErrorAction SilentlyContinue) { ollama pull gemma3:1b }
else { Write-Host "Optional: install Ollama from ollama.com and run 'ollama pull gemma3:1b' for one-line answers." }

Start-Process .\.venv\Scripts\pythonw.exe -ArgumentList "-m", "deja"
Write-Host "Déjà is running in the tray and will start at every sign-in. Remove that with: .venv\Scripts\python -m deja --uninstall"
