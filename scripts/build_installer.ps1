# Build Hold Assist installer for deployment to other PCs (no Cursor/Python on targets).
# Run on a BUILD machine only:
#   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
#
# Output: installer\output\HoldAssist-Setup.exe  (~500MB+, includes app + VAD model)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== Hold Assist Production Build ===" -ForegroundColor Cyan
Write-Host "Target PCs only need HoldAssist-Setup.exe - nothing else." -ForegroundColor Gray
Write-Host ""

function Get-PythonOrg {
    $found = & "$Root\scripts\find_python_org.ps1" 2>$null
    if ($LASTEXITCODE -eq 0 -and $found) { return $found.Trim() }
    return $null
}

$pythonOrg = Get-PythonOrg
if (-not $pythonOrg) {
    Write-Host "python.org Python not found. Installing via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.13 --accept-package-agreements --accept-source-agreements --silent
    $pythonOrg = Get-PythonOrg
}
if (-not $pythonOrg) {
    throw @"
python.org Python 3.10+ is required on THIS build PC only.
Install from https://www.python.org/downloads/ (not Microsoft Store)
Or run: winget install Python.Python.3.13
"@
}

Write-Host "Build Python: $pythonOrg" -ForegroundColor Green

# Fresh venv from python.org (Store Python breaks pystray/torch at runtime)
if (Test-Path ".venv") {
    Get-Process python*, HoldAssist* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $cfg = Get-Content ".venv\pyvenv.cfg" -Raw -ErrorAction SilentlyContinue
    if ($cfg -match "WindowsApps|PythonSoftwareFoundation") {
        Write-Host "Removing Store-Python venv..."
        try { Remove-Item -Recurse -Force ".venv" } catch {
            Rename-Item ".venv" ".venv.old_$(Get-Date -Format 'yyyyMMddHHmmss')" -Force
        }
    }
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating build virtual environment..."
    & $pythonOrg -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"
$venvCfg = Get-Content ".venv\pyvenv.cfg" -Raw
if ($venvCfg -match "WindowsApps|PythonSoftwareFoundation") {
    throw "venv still uses Microsoft Store Python. Delete .venv and re-run this script."
}

& $py -m pip install --upgrade pip -q
& $py -m pip install -r requirements.txt -q
& $py -m pip install pyinstaller -q

Write-Host "Building icons from icon.jpg (if present)..."
& $py scripts\generate_assets.py
if (-not (Test-Path "assets\icon.ico")) {
    throw "assets\icon.ico missing - add icon.jpg to project root and re-run."
}

Write-Host "Bundling Silero VAD model for offline install..."
& $py scripts\prepare_vad_bundle.py
if (-not (Test-Path "bundle\silero_vad")) {
    throw "VAD bundle failed - check internet on build machine once."
}

Write-Host "Running PyInstaller (5-15 minutes)..."
& $py -m PyInstaller --noconfirm --clean hold_assist.spec

$dist = Join-Path $Root "dist\HoldAssist"
if (-not (Test-Path "$dist\HoldAssist.exe")) {
    throw "Build failed: $dist\HoldAssist.exe not found"
}
Write-Host "App bundle: $dist" -ForegroundColor Green

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    Write-Host "Building installer..."
    & $iscc "installer\hold_assist.iss"
    $setup = Join-Path $Root "installer\output\HoldAssist-Setup.exe"
    if (Test-Path $setup) {
        $sizeMb = [math]::Round((Get-Item $setup).Length / 1MB, 1)
        Write-Host ""
        Write-Host "SUCCESS - deploy this file to user PCs:" -ForegroundColor Green
        Write-Host "  $setup  ($sizeMb MB)" -ForegroundColor Green
        Write-Host ""
        Write-Host "Users: run setup, pick audio output (e.g. Remote Audio), no Python/Cursor needed."
    }
} else {
    Write-Host "Inno Setup 6 not installed - zip dist\HoldAssist instead." -ForegroundColor Yellow
    Write-Host "https://jrsoftware.org/isinfo.php"
}

Write-Host "Done."
