# Publish the Windows installer (one-time + updates)

Source code is on GitHub, but **`HoldAssist-Setup.exe` is not in git** (too large). You attach it to a **GitHub Release** so the “download installer” links work.

## Why “latest release” was empty

- `git push` uploads **source only**
- [releases/latest](https://github.com/RetroCodeRamen/Hold-Assist/releases/latest) works only after you **create a release** and upload the `.exe`

Your installer is already built on this PC:

`installer\output\HoldAssist-Setup.exe` (~126 MB)

## Create the first release (browser)

1. Open: https://github.com/RetroCodeRamen/Hold-Assist/releases  
2. Click **Create a new release** (or **Draft a new release**)  
3. **Choose a tag:** `v1.2.0` → **Create new tag** on publish  
4. **Release title:** `Hold Assist 1.2.0`  
5. **Description:** e.g. “Windows installer. Local hold-music monitor. See README.”  
6. Under **Attach binaries**, drag or browse to:  
   `c:\Users\ajjones\OneDrive - Positive Tech Solutions\Documents\hold assist\installer\output\HoldAssist-Setup.exe`  
7. Click **Publish release**

After that, this link works for users:

https://github.com/RetroCodeRamen/Hold-Assist/releases/latest

## Optional: command line (after `gh auth login`)

```powershell
cd "c:\Users\ajjones\OneDrive - Positive Tech Solutions\Documents\hold assist"
gh auth login
gh release create v1.2.0 "installer\output\HoldAssist-Setup.exe" `
  --repo RetroCodeRamen/Hold-Assist `
  --title "Hold Assist 1.2.0" `
  --notes "Windows installer. Fully local; see README."
```

## Update README on GitHub (optional)

After publishing, you can change Download links back to `/releases/latest` if you prefer.
