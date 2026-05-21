# Recreate venv using python.org Python (fixes Store Python heap crashes).
# Run: powershell -ExecutionPolicy Bypass -File scripts\recreate_venv.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Find-PythonOrg {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            $v = & $p -c "import sys; print(sys.version)"
            if ($v -notmatch "Windows Store") { return $p }
        }
    }
    return $null
}

$py = Find-PythonOrg
if (-not $py) {
    Write-Host "python.org Python not found. Trying winget install..." -ForegroundColor Yellow
    winget install Python.Python.3.13 --accept-package-agreements --accept-source-agreements --silent 2>$null
    $py = Find-PythonOrg
}
if (-not $py) {
    Write-Host "Install Python from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "Or run: winget install Python.Python.3.13" -ForegroundColor Red
    Write-Host "Enable 'Add to PATH'. Do NOT use the Microsoft Store version."
    exit 1
}

Write-Host "Using: $py"
& $py --version

if (Test-Path ".venv") {
    Write-Host "Removing old .venv..."
    Get-Process python*, HoldAssist* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    try {
        Remove-Item -Recurse -Force ".venv"
    } catch {
        $backup = ".venv.old_$(Get-Date -Format 'yyyyMMddHHmmss')"
        Write-Host "Could not delete .venv (files in use). Renaming to $backup"
        Rename-Item ".venv" $backup -Force
    }
}

& $py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\generate_assets.py

Write-Host ""
Write-Host "Done. Run:  .\run_dev.bat" -ForegroundColor Green
& .\.venv\Scripts\python.exe -c "import sys; print('Executable:', sys.executable)"
