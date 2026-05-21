# Hold Assist — install on user PCs

**Users and IT do not need Cursor, Python, or the source code.**

## What to distribute

One file from the build computer:

**`HoldAssist-Setup.exe`**

(Build instructions for IT: **[BUILD.md](BUILD.md)**)

## Install (each user PC)

1. Run **`HoldAssist-Setup.exe`**.
2. Recommended installer options (checked by default):
   - **Start Hold Assist when you sign in to Windows** (runs in tray)
   - **Begin listening automatically at startup**
3. Finish the wizard.

## First-time setup (30 seconds)

1. Find **Hold Assist** in the system tray (near the clock). Double-click to open the window.
2. Under **Listen on output**, choose the device that plays the call:
   - **Remote Audio** — Windows 365 / cloud PC / RDP
   - **Headphones** or **Speakers** — local Teams/softphone
   - **Default** — matches Windows default playback
3. Click **Refresh** if you plug in a headset after the app started.
4. Click **Start** if listening did not begin automatically.

No internet is required on the user PC for the voice-detection model (it is included in the installer).

## Logs and support

If something fails, open:

```
%APPDATA%\HoldAssist\hold_assist.log
```

Settings file:

```
%APPDATA%\HoldAssist\settings.json
```

## Uninstall

Windows **Settings → Apps → Hold Assist → Uninstall**

## Command-line (optional)

Installed location is usually:

```
C:\Program Files\Hold Assist\HoldAssist.exe
```

| Flag | Purpose |
|------|---------|
| `--minimized` | Start in tray only |
| `--autostart` | Start listening when the app opens |

Sign-in shortcut uses: `--minimized --autostart`
