# Put Hold Assist on GitHub

Use this guide when **Git is installed** and you have created an **empty repo** on GitHub.

## Quick push (after Git is ready)

1. On GitHub: **+** → **New repository** → name e.g. **`Hold-Assist`** → **empty** (no README) → Create.
2. Copy the repo URL, e.g. `https://github.com/RetroCodeRamen/Hold-Assist.git`
3. In PowerShell:

```powershell
cd "c:\Users\ajjones\OneDrive - Positive Tech Solutions\Documents\hold assist"
powershell -ExecutionPolicy Bypass -File scripts\setup_github.ps1 `
  -RepoUrl "https://github.com/RetroCodeRamen/Hold-Assist.git" `
  -GitHubUser "RetroCodeRamen"
```

Replace `RetroCodeRamen` with your GitHub username. The script commits source code, updates README links, and pushes to `main`.

4. Tell your assistant (or follow step 4 below) to attach the installer to a **Release**.

---

## 1. Install Git (if needed)

Download **Git for Windows**: https://git-scm.com/download/win  

During setup, choose **"Git from the command line and also from 3rd-party software"**.

Optional (easier GitHub login): https://cli.github.com/

Verify:

```powershell
git --version
```

## 2. Create an empty repo on GitHub

1. Sign in to https://github.com  
2. **+** → **New repository**  
3. Name: **`Hold-Assist`** (no spaces)  
4. **Empty** — do not add README, license, or .gitignore (this project already has them)  
5. **Create repository**  
6. Copy the HTTPS URL: `https://github.com/RetroCodeRamen/Hold-Assist.git`

**Private vs public**

- **Private** — only you and invited collaborators  
- **Public** — anyone can see source; good for feedback and issues  

## 3. What gets pushed vs what stays local

| Included in Git | Not committed (see `.gitignore`) |
|-----------------|----------------------------------|
| Source `.py`, scripts, installer `.iss` | `.venv/` |
| `README.md`, `SECURITY.md`, docs | `dist/`, `build/` |
| `icon.jpg`, `LICENSE` | `bundle/` (built during `build.bat`) |
| `requirements.txt`, `hold_assist.spec` | `installer/output/HoldAssist-Setup.exe` |

The **installer exe** is too large for normal git history—upload it to **Releases** instead.

## 4. Publish the installer (Releases)

End users should download **`HoldAssist-Setup.exe`**, not clone Python dependencies.

1. On your build PC (if needed):

   ```powershell
   .\build.bat
   ```

2. GitHub repo → **Releases** → **Create a new release**  
3. Tag: `v1.2.0`  
4. Title: `Hold Assist 1.2.0`  
5. Attach: `installer\output\HoldAssist-Setup.exe`  
6. **Publish release**  

User download link:

`https://github.com/RetroCodeRamen/Hold-Assist/releases/latest`

## 5. Authentication when pushing

| Method | Notes |
|--------|--------|
| **GitHub CLI** | `gh auth login` then push |
| **Personal Access Token** | Use token as password when `git push` asks |
| **SSH** | `git@github.com:USER/Hold-Assist.git` with SSH key configured |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `git` not recognized | Install Git, restart PowerShell |
| Push rejected / auth failed | PAT or `gh auth login` |
| File too large | Do not commit `dist/` or `.venv/` — check `.gitignore` |
| OneDrive conflicts | Consider `C:\dev\Hold-Assist` if sync causes lock errors |

## After the first push

- Open **Issues** on GitHub for feature suggestions  
- Optionally enable **Discussions** for feedback  
- Re-run `setup_github.ps1` only for new remotes; use normal `git add` / `commit` / `push` for updates  
