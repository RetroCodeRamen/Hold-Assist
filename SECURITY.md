# Security and privacy — Hold Assist

## What the app does (data handling)

- **Listens only to speaker/headphone output** (WASAPI loopback), not your microphone. The app refuses to record from a non-loopback device.
- **All processing is local.** Audio chunks are analyzed in memory for voice activity; nothing is uploaded, recorded to disk, or sent over the network at runtime.
- **No telemetry, updates, or remote commands** are implemented in the application code.
- **Settings** are stored in `%APPDATA%\HoldAssist\settings.json` (thresholds, device id, preferences only).
- **Logs** (`%APPDATA%\HoldAssist\hold_assist.log` when installed) may contain device names and errors, not audio content.

## Optional behaviors (user-controlled)

- **Sign-in startup** — installer can add a shortcut under your user Startup folder (`--minimized --autostart`). You can remove it in Settings or uninstall.
- **Debug mode** — prints VAD scores to the console; leave off for normal use.

## Threat model (honest limits)

| Risk | Notes |
|------|--------|
| Eavesdropping on calls | Anyone with access to your PC could already capture audio; this app does the same locally for hold detection. Do not install on shared machines you do not trust. |
| Malicious replacement of installer | Distribute `HoldAssist-Setup.exe` from a trusted channel (your GitHub Release, internal share). Prefer HTTPS and checksums for downloads. |
| Supply chain (build time) | The Silero VAD model is downloaded once on the **build** machine from [snakers4/silero-vad](https://github.com/snakers4/silero-vad) and bundled into the installer. Rebuild from this repo after dependency updates. |
| Corporate policy | Some employers prohibit call-audio tools; check policy before use. |

## Antivirus and SmartScreen

PyInstaller + large ML libraries often trigger **false positives** (e.g. “trojan generic”, “PUA”) even when the app is benign.

**Reduce false positives:**

1. **Code-sign** `HoldAssist-Setup.exe` with an Authenticode certificate (EV helps SmartScreen reputation faster).
2. **Do not use UPX** — the project spec sets `upx=False` for this reason.
3. **Submit** the signed (or unsigned) installer to [VirusTotal](https://www.virustotal.com) before wide release; fix only if *your* build is flagged and you can reproduce on a clean VM.
4. **Report false positives** to vendors (Microsoft, etc.) with file hash and publisher URL.
5. **Publish** install instructions and source on GitHub so users can verify behavior.

**Behaviors that can look “suspicious” to heuristics (but are intentional):**

- Background process + system tray
- Optional login startup (persistence)
- Audio capture APIs (loopback)
- Large unsigned executable (~100–200 MB)

There is no way to offer hold-music monitoring without audio access; signing and transparency are the main mitigations.

## Reporting security issues

If you find a vulnerability in this project, open a private issue or contact the maintainer with steps to reproduce. Do not post exploit details publicly before a fix is available.
