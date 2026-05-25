# Deployment Guide

From zero to a live public dashboard in ~10 minutes.

---

## Part 1 — Create the GitHub Repository

1. Open [github.com/new](https://github.com/new) in your browser.

2. Fill in:
   - **Repository name:** `freetour-tracker`
   - **Visibility:** Public *(required for Streamlit Cloud free tier and for the raw CSV URL)*
   - Leave "Initialize with README" **unchecked** — the local folder already has content.

3. Click **Create repository**.

4. Copy your GitHub username from the URL. You will need it in the next steps.

---

## Part 2 — Connect Your Local Folder to GitHub

Open Terminal and run these commands one by one.

```bash
cd /Users/mac/freetour-tracker

# Tell git who you are (only needed once per machine)
git config user.name  "Your Name"
git config user.email "your@email.com"

# Point the local repo at GitHub
git remote add origin https://github.com/YOUR_USERNAME/freetour-tracker.git

# Create the initial commit
git add rankings.csv chart.png tracker.py dashboard.py requirements.txt .gitignore DEPLOY.md setup.sh cron_setup.sh cron_remove.sh
git commit -m "initial commit"

# Push everything
git push -u origin main
```

> **Authentication tip:** GitHub no longer accepts passwords over HTTPS.
> When prompted, use a **Personal Access Token** instead of your password.
> Create one at: Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
> Grant it the **repo** scope. Paste it as the password when git asks.

---

## Part 3 — Update the Dashboard with Your Repo URL

1. Open `dashboard.py` in a text editor.

2. Find this line near the top:

   ```python
   GITHUB_RAW_URL = (
       "https://raw.githubusercontent.com/YOUR_USERNAME/freetour-tracker/main/rankings.csv"
   )
   ```

3. Replace `YOUR_USERNAME` with your actual GitHub username. Example:

   ```python
   GITHUB_RAW_URL = (
       "https://raw.githubusercontent.com/lucasbrag/freetour-tracker/main/rankings.csv"
   )
   ```

4. Save the file, then commit and push:

   ```bash
   cd /Users/mac/freetour-tracker
   git add dashboard.py
   git commit -m "set github raw url"
   git push
   ```

---

## Part 4 — Preview the Dashboard Locally (Optional)

```bash
cd /Users/mac/freetour-tracker
source .venv/bin/activate
pip install streamlit plotly -q
streamlit run dashboard.py
```

Streamlit will open `http://localhost:8501` in your browser.

---

## Part 5 — Deploy to Streamlit Cloud (Free)

Streamlit Cloud hosts public dashboards for free with no credit card required.

### 5.1 Sign up

Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.

### 5.2 Create a new app

1. Click **"New app"**.
2. Fill in:
   - **Repository:** `YOUR_USERNAME/freetour-tracker`
   - **Branch:** `main`
   - **Main file path:** `dashboard.py`
3. Leave all other fields at their defaults.
4. Click **Deploy!**

Streamlit will install the packages from `requirements.txt` and start the app.
First deployment takes about 2–3 minutes.

### 5.3 Get your public URL

Once deployed, Streamlit gives you a URL like:

```
https://YOUR_USERNAME-freetour-tracker-dashboard-XXXXX.streamlit.app
```

That URL is public — anyone with the link can view the dashboard without logging in.

---

## Part 6 — Share the URL

Send the Streamlit URL to your team. The dashboard:

- Reads `rankings.csv` directly from GitHub (no server needed)
- Refreshes automatically when `rankings.csv` is updated
- Updates once per day when the cron job runs at 9:00 AM and pushes new data

---

## How the Full Pipeline Works

```
Every day at 9:00 AM
        │
        ▼
  tracker.py runs
  (headless Chromium)
        │
        ▼
  Scrapes freetour.com/paris
  with English + Walking Tour filters
        │
        ▼
  Appends row to rankings.csv
  Saves chart.png
        │
        ▼
  git commit + push to GitHub
        │
        ▼
  dashboard.py reads new rankings.csv
  from GitHub raw URL
        │
        ▼
  Team sees updated positions
  on Streamlit dashboard
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `git push` asks for password and fails | Use a Personal Access Token instead (see Part 2 tip) |
| Dashboard shows "Could not load data" | Check that `GITHUB_RAW_URL` has your correct username and the repo is public |
| Streamlit shows an old `requirements.txt` error | Make sure `requirements.txt` is committed and pushed |
| Cron job doesn't run | macOS may need Full Disk Access for cron — check System Settings → Privacy & Security → Full Disk Access, add `/usr/sbin/cron` |
| Tours not found after a site redesign | Run `DEBUG=1 python tracker.py` to save `debug.png` for inspection |
