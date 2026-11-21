# Deploying to GitHub and Streamlit Community Cloud

Two parts:
- **Part A - GitHub** stores your code (needed for submission and for Part B).
- **Part B - Streamlit Community Cloud** (free) gives you a public link to the app.

> The online version can show the Dashboard, Monitoring Reports and **Image Upload** detection.
> **The drone cannot be flown from the online version**: the cloud server is not on the Tello's Wi-Fi.
> The app detects this and shows a note instead of the Live Camera. Fly the drone by running locally.

---

## Before you start (do this once)

1. **Copy your model into the project:**
   `C:\Users\seela\Documents\Term4\water_quality\weights\best.pt` -> `weights\best.pt` inside this folder.
   Without it the online app shows "Model weights not found".
2. Check the file size (right-click > Properties). It must be **under 100 MB** (GitHub's limit).
3. Install **Git for Windows**: https://git-scm.com/download/win (keep the default options).
4. Create a free account at https://github.com if you do not have one.

The project already contains a `.gitignore`, so your `venv`, database, evidence photos and `__pycache__`
are **not** uploaded (uploading `venv` is the most common cause of failed pushes).

---

## Part A - Upload to GitHub

1. On github.com click **New repository**. Name it `water-quality-monitor`.
   Leave "Add a README" **unticked** (the project has one; ticking it causes a push conflict).
   Choose Public (required for the free Streamlit Cloud) and click **Create repository**.
2. Open Command Prompt in the project folder and run, one line at a time
   (replace `YOUR-USERNAME`):

```bat
cd C:\Users\seela\Documents\Term4\water_quality_monitor
git init
git config user.name "Your Name"
git config user.email "you@example.com"
git add .
git status
```

3. Check the `git status` list: you should see `app.py`, `config.py`, `core/`, `ui/`, `views/`,
   `weights/best.pt`, `requirements.txt`, `.streamlit/config.toml`. You should **not** see `venv/` or `data/water_quality.db`.
4. Commit and push:

```bat
git commit -m "Water quality monitoring system"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/water-quality-monitor.git
git push -u origin main
```

A browser window opens asking you to sign in to GitHub the first time. Approve it and the push finishes.

**Later changes:**

```bat
git add .
git commit -m "Describe what changed"
git push
```

---

## Part B - Put the app online (Streamlit Community Cloud)

1. Go to https://share.streamlit.io and sign in **with GitHub**.
2. Click **Create app** > **Deploy a public app from GitHub**.
3. Fill in:
   - Repository: `YOUR-USERNAME/water-quality-monitor`
   - Branch: `main`
   - Main file path: `app.py`
4. Open **Advanced settings** and choose **Python 3.11** (or 3.12). Save.
5. Click **Deploy**. The first build takes 5-10 minutes (it installs PyTorch). Watch the log at the bottom right.

When it finishes you get a link like `https://water-quality-monitor.streamlit.app`.

**Note:** the online database and evidence photos are temporary. They reset when the app restarts or
sleeps (free apps sleep after a few days without visitors; anyone can wake them with one click).

---

## Fixing common errors

| Error | Cause | Fix |
|---|---|---|
| `remote: Repository not found` | Wrong username/repo name in the URL | `git remote set-url origin https://github.com/YOUR-USERNAME/water-quality-monitor.git` |
| `failed to push some refs` / `rejected (fetch first)` | Repo was created with a README | `git pull origin main --allow-unrelated-histories`, then `git push` |
| `File ... exceeds GitHub's file size limit of 100.00 MB` | `best.pt` or `venv` too big | Make sure `venv` is not committed; for a big model use Git LFS (`git lfs install`, `git lfs track "*.pt"`) |
| `Model weights not found` (online) | `weights/best.pt` not uploaded | Copy it into `weights/`, then `git add weights/best.pt`, commit, push |
| `ImportError: libGL.so.1` (online) | Normal OpenCV installed instead of headless | `requirements.txt` must use `ultralytics-opencv-headless` and `opencv-python-headless` (already done). Then in the Streamlit app menu choose **Reboot app** |
| Build runs out of memory/space | Full GPU PyTorch | Keep the `--extra-index-url .../whl/cpu` line at the top of `requirements.txt` (already done) |
| `ModuleNotFoundError` (online) | Package missing from requirements | Add it to `requirements.txt`, push, the app rebuilds automatically |

## Running locally after these changes

The requirements now use the headless OpenCV and CPU PyTorch, which work the same on Windows.
If you already have a working `venv`, you do not need to reinstall. For a fresh setup:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
