# Build CLI exe with PyInstaller
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Installing PyInstaller (if needed)"
python -m pip install -q "pyinstaller>=6.0" PyNaCl

Write-Host "==> Cleaning old build/dist"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$Root\build\pyinstaller"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$Root\dist\turb-gpt-register"
Remove-Item -Force -ErrorAction SilentlyContinue "$Root\dist\turb-gpt-register.exe"

Write-Host "==> Running PyInstaller"
python -m PyInstaller `
  --noconfirm `
  --clean `
  --distpath "$Root\dist" `
  --workpath "$Root\build\pyinstaller" `
  "$Root\build\turb_gpt_register.spec"

Write-Host "==> Writing sidecar .env / README (UTF-8 via Python)"
python "$Root\tools\write_dist_sidecars.py"

Write-Host "==> Done. Output: $Root\dist\turb-gpt-register.exe"
Get-ChildItem "$Root\dist" | Format-Table Name, Length
