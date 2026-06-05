# Haraj Corvette Monitor

Monitors [Haraj](https://haraj.com.sa) for new Corvette car listings and sends Discord alerts instantly. Scrapes the search results page every 10 minutes and filters out parts, rims, and accessories — only real car listings come through.

## How it works

| Component | Detail |
|-----------|--------|
| Source | Scrapes `haraj.com.sa/search/كورفيت` (server-rendered HTML) |
| Schedule | Every 10 minutes via GitHub Actions cron, or `run.bat` on a local PC |
| Filtering | Skips listings whose title contains part/accessory keywords (rims, tires, seats, etc.) |
| State | `seen_listings.json` tracks alerted IDs so you never get duplicate alerts |
| Alerts | Discord rich embed via webhook |

## Repo structure

```
haraj_monitor.py          # main script — scrape, filter, alert, exit
requirements.txt          # pip dependencies (requests, beautifulsoup4)
run.bat                   # run locally on Windows (loops every 10 min)
seen_listings.json        # auto-managed state file (do not edit manually)
.github/
  workflows/
    monitor.yml           # GitHub Actions workflow
```

---

## Setup — GitHub Actions (recommended)

Runs in the cloud automatically. No PC needs to stay on.

### 1. Fork / clone the repo

```bash
git clone https://github.com/G0glan/haraj-corvette-monitor.git
cd haraj-corvette-monitor
```

### 2. Add the Discord Webhook secret

1. Go to your repo on GitHub → **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `DISCORD_WEBHOOK_URL`
4. Value: your Discord webhook URL
5. Click **Add secret**

### 3. Enable Actions

Go to the **Actions** tab and confirm workflows are enabled.

### 4. Test with a manual run

1. **Actions** tab → **Haraj Corvette Monitor** → **Run workflow**
2. Check the run logs and your Discord channel

> **Note:** On the first run all current listings are sent as alerts (they're all "new"). From the second run onwards only genuinely new listings trigger alerts.

---

## Setup — Local PC (alternative)

Use this if you want to run it on a specific machine (e.g. a PC in Saudi Arabia).

### Requirements

- Python 3.8+ — [python.org](https://python.org) (tick **Add to PATH** during install)

### Run

Double-click `run.bat`. Leave the window open.

```
Installing dependencies...
Starting Haraj Corvette Monitor...
Leave this window open. Press Ctrl+C to stop.
```

The script polls every 10 minutes and exits between runs — no background process, no browser needed.

---

## Customising the keyword filter

Open `haraj_monitor.py` and edit the `EXCLUDE_KEYWORDS` list near the top. Any listing whose title contains one of these Arabic words is silently skipped:

```python
EXCLUDE_KEYWORDS = [
    "جنوط",      # rims (colloquial)
    "رنج",       # rims / wheels
    "إطار",      # tire
    ...
]
```

Add a word, save, and push — the next run picks it up automatically.

## Changing the search keyword

Edit `SEARCH_KEYWORD` in `haraj_monitor.py`:

```python
SEARCH_KEYWORD = "كورفيت"   # Arabic for "Corvette"
```

## Using a proxy

If the script can't reach Haraj, set a `PROXY_URL` environment variable (or GitHub Actions secret):

```
PROXY_URL=http://user:pass@host:port
```

The script picks it up automatically — no code changes needed.
