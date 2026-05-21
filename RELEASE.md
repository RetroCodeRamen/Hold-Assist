# Publish a download for GitHub Releases

Source code is on GitHub, but **installers are not in git** (too large). You attach a file to a **GitHub Release** so download links work.

## Why the assistant could push code but not create a release

| Action | Tool | What it needs |
|--------|------|----------------|
| **Push source** (`git push`) | Git | Credentials in Windows (worked — used your cached GitHub login) |
| **Create a release + upload .zip/.exe** | GitHub website or `gh` CLI | **Separate** login to GitHub’s Releases API |

Releases are **not** part of `git push`. Uploading `HoldAssist-Portable.zip` requires:

1. You signed in on GitHub (browser or `gh auth login` as **RetroCodeRamen**), and  
2. A manual upload on the Releases page, or `gh release create` with that login.

The automated push from Cursor had **no `gh auth login`** for your RetroCodeRamen account, so release upload could not run non-interactively.

## Why “latest release” was empty

- `git push` only uploads **source**
- [releases/latest](https://github.com/RetroCodeRamen/Hold-Assist/releases/latest) works only after you **publish** a release with an attached file

## Files on this PC (pick one or both)

| File | Size | User experience |
|------|------|-----------------|
| **`installer\output\HoldAssist-Portable.zip`** | ~192 MB | Unzip anywhere → run `HoldAssist.exe` (no installer wizard) |
| `installer\output\HoldAssist-Setup.exe` | ~126 MB | Standard Windows setup (tray, startup shortcuts) |

**Portable zip is fine for v1.2.0** — good choice if you want a quick release now.

## Create the first release (browser) — portable zip

1. Open: https://github.com/RetroCodeRamen/Hold-Assist/releases  
2. Sign in as **RetroCodeRamen** (not your work account).  
3. **Create a new release**  
4. **Tag:** `v1.2.0` (create on publish)  
5. **Title:** `Hold Assist 1.2.0`  
6. **Description (example):**  
   > Portable build: download zip, unzip, run `HoldAssist.exe`. Fully local; see README.  
7. **Attach:** drag  
   `installer\output\HoldAssist-Portable.zip`  
8. **Publish release**

Then this link works:

https://github.com/RetroCodeRamen/Hold-Assist/releases/latest

## Optional: command line (after `gh auth login` as RetroCodeRamen)

```powershell
cd "c:\Users\ajjones\OneDrive - Positive Tech Solutions\Documents\hold assist"
gh auth login
gh release create v1.2.0 "installer\output\HoldAssist-Portable.zip" `
  --repo RetroCodeRamen/Hold-Assist `
  --title "Hold Assist 1.2.0 (portable)" `
  --notes "Unzip and run HoldAssist.exe. Fully local hold monitor. See README."
```

You can attach **both** zip and setup exe on the same release later if you want.
