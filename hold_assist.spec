# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Hold Assist Windows bundle

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)
datas = [(str(root / "assets"), "assets")]
_vad_bundle = root / "bundle" / "silero_vad"
if _vad_bundle.is_dir():
    datas.append((str(_vad_bundle), "silero_vad"))
else:
    raise SystemExit(
        "Missing bundle/silero_vad. Run: python scripts/prepare_vad_bundle.py"
    )

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "audio_devices",
        "tray_icon",
        "icon_build",
        "torch",
        "torchaudio",
        "soundcard",
        "pystray",
        "PIL",
        "plyer",
        "plyer.platforms.win.notification",
        "win10toast",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HoldAssist",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed PyInstaller builds are often flagged by AV heuristics
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "icon.ico") if (root / "assets" / "icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HoldAssist",
)
