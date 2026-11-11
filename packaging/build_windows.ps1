# Builds "dist\GHOST AI\GHOST AI.exe" and a portable zip.
# Usage (PowerShell, from the repo root):  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -e ".[dev]"
& $py -m pip install "llama-cpp-python>=0.3.16" --only-binary=:all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

& $py -m pytest
if ($LASTEXITCODE -ne 0) { throw "Tests failed - not building." }

& $py tools\make_icons.py
& $py -m PyInstaller packaging\ghost_ai.spec --noconfirm --clean --distpath dist --workpath build
$env:GHOST_SELFTEST = "1"; $env:GHOST_AI_HOME = "$PWD\build\selftest"
$p = Start-Process "dist\GHOST AI\GHOST AI.exe" -PassThru -Wait
Remove-Item Env:GHOST_SELFTEST, Env:GHOST_AI_HOME
if ($p.ExitCode -ne 0) { throw "Frozen build cannot load the built-in AI engine - see build\selftest\logs" }

$version = (& $py -c "import ghost_ai; print(ghost_ai.__version__)").Trim()
$zip = "dist\GHOST-AI-$version-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\GHOST AI" -DestinationPath $zip
Write-Host "Built: dist\GHOST AI\GHOST AI.exe"
Write-Host "Zip:   $zip"
