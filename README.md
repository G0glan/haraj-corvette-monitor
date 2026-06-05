# Haraj Corvette Monitor

Polls the [Haraj](https://haraj.com.sa) GraphQL API every 10 minutes for new
Corvette listings and sends Discord Webhook alerts for any new results.
Runs entirely on GitHub Actions — no server required.

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2. Add the Discord Webhook secret

1. Open your repository on GitHub.
2. Go to **Settings → Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Name: `DISCORD_WEBHOOK_URL`
5. Value: your Discord webhook URL (e.g. `https://discord.com/api/webhooks/...`)
6. Click **Add secret**.

### 3. Enable Actions (if not already enabled)

Go to the **Actions** tab of your repository and confirm that workflows are
enabled.

### 4. Trigger a manual test run

1. Open the **Actions** tab.
2. Select **Haraj Corvette Monitor** in the left sidebar.
3. Click **Run workflow → Run workflow**.
4. Watch the run complete and check your Discord channel for alerts.

## How it works

| Component | Detail |
|-----------|--------|
| Schedule | Every 10 minutes via `*/10 * * * *` cron |
| Language | Python 3.11 |
| State file | `seen_listings.json` — tracks listing IDs that have already been alerted |
| Auto-commit | After each run the bot commits `seen_listings.json` back to the repo so state persists across runs. Commits are tagged `[skip ci]` to avoid triggering recursive workflow runs. |
| Alerting | Discord rich embed via webhook |

## Repo structure

```
haraj_monitor.py          # main script (single-poll, exits cleanly)
requirements.txt          # pip dependencies
seen_listings.json        # auto-managed by the bot (do not edit manually)
.github/
  workflows/
    monitor.yml           # GitHub Actions workflow
```

## Local development

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python haraj_monitor.py
```

The script runs one poll and exits. Run it again (or via a local cron job) to
simulate the GitHub Actions schedule.
