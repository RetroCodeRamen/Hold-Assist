# Returns path to python.org Python (not Microsoft Store). Exits 1 if missing.
$paths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
)
foreach ($p in $paths) {
    if (Test-Path $p) {
        $cfg = & $p -c "import sys; print(sys.executable)" 2>$null
        if ($cfg -and $cfg -notmatch "WindowsApps") {
            Write-Output $p
            exit 0
        }
    }
}
exit 1
