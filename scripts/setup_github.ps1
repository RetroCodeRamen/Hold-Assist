# Initialize git and push Hold Assist to GitHub.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_github.ps1 `
#     -RepoUrl "https://github.com/USER/hold-assist.git" `
#     -GitHubUser "USER"

param(
    [Parameter(Mandatory = $true)]
    [string] $RepoUrl,
    [string] $GitHubUser = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Find-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { return "git" }
    $paths = @(
        "${env:ProgramFiles}\Git\cmd\git.exe",
        "${env:ProgramFiles(x86)}\Git\cmd\git.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    throw "Git not found. Install from https://git-scm.com/download/win then re-run this script."
}

function Get-GitHubUserFromUrl {
    param([string] $Url)
    if ($Url -match "github\.com[:/]([^/]+)/") {
        return $Matches[1]
    }
    return ""
}

function Get-RepoNameFromUrl {
    param([string] $Url)
    if ($Url -match "github\.com[:/][^/]+/([^/.]+)") {
        return $Matches[1]
    }
    return "hold-assist"
}

$git = Find-Git
Write-Host "Using: $git" -ForegroundColor Cyan

if (-not $GitHubUser) {
    $GitHubUser = Get-GitHubUserFromUrl -Url $RepoUrl
}
$repoName = Get-RepoNameFromUrl -Url $RepoUrl
if ($GitHubUser) {
    Write-Host "Updating docs: user=$GitHubUser repo=$repoName" -ForegroundColor Cyan
    $files = @("README.md", "GITHUB.md", "INSTALL.md")
    foreach ($name in $files) {
        $path = Join-Path $Root $name
        if (Test-Path $path) {
            $text = Get-Content $path -Raw -Encoding UTF8
            $text = $text -replace "YOUR_USERNAME", $GitHubUser
            $text = $text -replace "hold-assist", $repoName
            Set-Content -Path $path -Value $text -Encoding UTF8 -NoNewline
        }
    }
}

if (-not (Test-Path ".git")) {
    & $git init
    & $git branch -M main
}

# Block accidental huge commits (after init)
$badPaths = @("dist", "build", ".venv", "installer\output", "bundle")
foreach ($bad in $badPaths) {
    $tracked = & $git ls-files $bad 2>$null
    if ($tracked) {
        throw "Path '$bad' is tracked by git but should be ignored. Run: git rm -r --cached $bad"
    }
}

& $git add -A
& $git status

$status = & $git status --porcelain
if (-not $status) {
    Write-Host "Nothing to commit (already up to date?)." -ForegroundColor Yellow
} else {
    & $git commit -m @"
Initial commit: Hold Assist

Windows hold-music monitor with local pickup alerts.
Fully offline at runtime; see README and SECURITY.md.
"@
}

$remotes = & $git remote 2>$null
if ($remotes -match "origin") {
    & $git remote set-url origin $RepoUrl
} else {
    & $git remote add origin $RepoUrl
}

Write-Host "Pushing to $RepoUrl ..." -ForegroundColor Cyan
& $git push -u origin main

Write-Host ""
Write-Host "Done. Open your repo on GitHub." -ForegroundColor Green
if ($GitHubUser) {
    Write-Host "  https://github.com/$GitHubUser/$repoName" -ForegroundColor Green
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run .\build.bat (if installer not built yet)" -ForegroundColor Yellow
Write-Host "  2. GitHub -> Releases -> upload installer\output\HoldAssist-Setup.exe" -ForegroundColor Yellow
