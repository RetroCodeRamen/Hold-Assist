"""
Download Silero VAD once on the BUILD machine and copy into bundle/ for PyInstaller.

End-user PCs then do not need internet or Cursor to obtain the model.
Run automatically from scripts/build_installer.ps1
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "bundle" / "silero_vad"
CACHE_DIR = Path.home() / ".cache" / "torch" / "hub"


def main() -> int:
    print("Downloading / caching Silero VAD (build machine only)...")
    import torch

    torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        trust_repo=True,
    )

    candidates = list(CACHE_DIR.glob("snakers4_silero-vad*"))
    if not candidates:
        print("ERROR: torch hub cache not found after download.", file=sys.stderr)
        return 1

    src = max(candidates, key=lambda p: p.stat().st_mtime)
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    shutil.copytree(src, BUNDLE_DIR)
    print(f"VAD bundle ready: {BUNDLE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
