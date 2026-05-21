# Building Hold Assist for other PCs

**End-user machines do not need:** Cursor, Python, git, or this source folder.  
They only run **`HoldAssist-Setup.exe`**.

Only **one build computer** needs the items below.

## Build computer requirements (once)

| Requirement | Notes |
|-------------|--------|
| Windows 10/11 | Same OS family as users |
| **python.org** Python 3.10+ | **Not** Microsoft Store Python |
| Internet | Once, to download PyTorch + Silero during build |
| [Inno Setup 6](https://jrsoftware.org/isinfo.php) | Creates `HoldAssist-Setup.exe` |

Install Python (if missing):

```powershell
winget install Python.Python.3.13
```

## Build steps

1. Copy the whole `hold assist` folder to the build PC (or clone from git).
2. Place your branding image as **`icon.jpg`** in the project root (optional; placeholder used if missing).
3. Run either:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
```

or double-click **`build.bat`**.

4. Wait 5–20 minutes (PyInstaller + large dependencies).
5. Ship this file to users:

```
installer\output\HoldAssist-Setup.exe
```

## What the build script does automatically

- Uses **python.org** Python only (rejects Store Python)
- Creates/refreshes `.venv` on the build machine
- Builds `icon.ico` / `icon.png` from `icon.jpg`
- Downloads and **bundles** the Silero VAD model (users stay offline)
- Runs PyInstaller → `dist\HoldAssist\`
- Runs Inno Setup → `installer\output\HoldAssist-Setup.exe`

## Troubleshooting the build

| Problem | Fix |
|---------|-----|
| Store Python / venv errors | `powershell -File scripts\recreate_venv.ps1` then rebuild |
| Missing `bundle/silero_vad` | Build machine needs internet once; re-run build script |
| Inno Setup not found | Install Inno Setup 6, or zip `dist\HoldAssist` manually |
| Build is huge (~500MB+) | Normal — includes PyTorch CPU |

## Developer testing (not for end users)

```powershell
.\run_dev.bat
```

Uses source + `.venv` on the build/dev PC only.

## User rollout

See **[INSTALL.md](INSTALL.md)** — pass `HoldAssist-Setup.exe` to IT or users.
