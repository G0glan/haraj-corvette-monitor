"""
haraj_monitor.py
────────────────────────────────────────────────────────────────
Monitors Haraj (haraj.com.sa) for new C6 Corvette listings via
their GraphQL API and sends formatted Discord Webhook alerts.

Requirements:
    pip install requests

Usage:
    1. Set DISCORD_WEBHOOK_URL below (or export as env variable).
    2. Optionally add proxies to the PROXIES dict.
    3. python haraj_monitor.py
────────────────────────────────────────────────────────────────
"""

import json
import os
import random
import time
import logging
from datetime import datetime
from pathlib import Path

import requests

# ─────────────────────────────────────────────
#  CONFIGURATION  (edit these)
# ─────────────────────────────────────────────

# Discord Webhook URL — set here or via environment variable:
# export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1512564674711912538/b-LFXo21zWpj4RXIUEK1HBfl-oYuHbsIjUZg6Wdfj9N2OL4vzCx31DfsR5eycZ4Im-wY"
)

# Search keyword (Arabic for "Corvette")
SEARCH_KEYWORD = "كورفيت"

# GraphQL endpoint
GRAPHQL_URL = "https://graphql.haraj.com.sa/"

# File to persist seen listing IDs between runs
STATE_FILE = Path("seen_listings.json")

# Poll interval: random seconds between MIN and MAX (default: 5–10 minutes)
SLEEP_MIN = 5 * 60   # 5 minutes
SLEEP_MAX = 10 * 60  # 10 minutes

# Request timeout in seconds
REQUEST_TIMEOUT = 20

# ─────────────────────────────────────────────
#  PROXY CONFIGURATION
#  Add your rotating residential proxies here.
#  Leave empty dict {} to disable proxies.
#  Example:
#    PROXIES = {
#        "http":  "http://user:pass@proxy-host:port",
#        "https": "http://user:pass@proxy-host:port",
#    }
# ─────────────────────────────────────────────
PROXIES = {}

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  HTTP HEADERS  (mimics a real desktop browser)
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Origin": "https://haraj.com.sa",
    "Referer": "https://haraj.com.sa/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


# ─────────────────────────────────────────────
#  GRAPHQL PAYLOAD
# ─────────────────────────────────────────────
def build_graphql_payload(keyword: str, page: int = 1) -> dict:
    """
    Builds the GraphQL request payload for searching Haraj listings.
    The query targets the standard search fields used by the Haraj web app.
    """
    return {
        "operationName": "searchPosts",
        "variables": {
            "query": keyword,
            "page": page,
            "size": 30,          # listings per page
            "sort": "date",      # newest first
        },
        "query": """
            query searchPosts($query: String!, $page: Int, $size: Int, $sort: String) {
              postSearch(query: $query, page: $page, size: $size, sort: $sort) {
                results {
                  id
                  title
                  price
                  city
                  date
                  authorName
                  bodyHTML
                }
                total
                page
              }
            }
        """,
    }


# ─────────────────────────────────────────────
#  STATE MANAGEMENT  (seen_listings.json)
# ─────────────────────────────────────────────
def load_seen_ids() -> set:
    """Loads the set of already-alerted listing IDs from disk."""
    if not STATE_FILE.exists():
        return set()
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(i) for i in data.get("seen_ids", []))
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("Could not parse %s (%s). Starting fresh.", STATE_FILE, exc)
        return set()


def save_seen_ids(seen_ids: set) -> None:
    """Persists the updated set of seen listing IDs to disk."""
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump({"seen_ids": list(seen_ids)}, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
#  HARAJ API  —  fetch listings
# ─────────────────────────────────────────────
def fetch_listings(keyword: str) -> list[dict]:
    """
    Sends a GraphQL POST request to Haraj and returns a list of
    raw listing dicts. Returns an empty list on any failure.
    """
    payload = build_graphql_payload(keyword)
    try:
        response = requests.post(
            GRAPHQL_URL,
            headers=HEADERS,
            json=payload,
            proxies=PROXIES or None,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        log.error("Request timed out after %s seconds.", REQUEST_TIMEOUT)
        return []
    except requests.exceptions.ProxyError as exc:
        log.error("Proxy error: %s", exc)
        return []
    except requests.exceptions.RequestException as exc:
        log.error("Network error: %s", exc)
        return []

    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        log.error("Failed to decode JSON response: %s", exc)
        return []

    # Navigate the expected GraphQL response shape safely
    try:
        results = body["data"]["postSearch"]["results"]
        if not isinstance(results, list):
            raise ValueError("'results' is not a list.")
        return results
    except (KeyError, TypeError, ValueError) as exc:
        log.error(
            "Unexpected API response shape — Haraj may have changed their schema. (%s)",
            exc,
        )
        log.debug("Raw response body: %s", json.dumps(body, ensure_ascii=False)[:500])
        return []


# ─────────────────────────────────────────────
#  LISTING PARSER
# ─────────────────────────────────────────────
def parse_listing(raw: dict) -> dict | None:
    """
    Extracts and normalises fields from a raw Haraj listing dict.
    Returns None if the listing ID cannot be determined.
    """
    listing_id = str(raw.get("id", "")).strip()
    if not listing_id:
        return None

    title    = raw.get("title", "No title")
    price    = raw.get("price")
    city     = raw.get("city", "Unknown")
    date_raw = raw.get("date", "")
    author   = raw.get("authorName", "Unknown")

    # Format price
    if price:
        try:
            price_str = f"{int(price):,} SAR"
        except (ValueError, TypeError):
            price_str = str(price)
    else:
        price_str = "Not listed"

    # Format date
    if date_raw:
        try:
            # Haraj typically returns Unix timestamps (seconds)
            dt = datetime.utcfromtimestamp(int(date_raw))
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError, OSError):
            date_str = str(date_raw)
    else:
        date_str = "Unknown"

    url = f"https://haraj.com.sa/{listing_id}"

    return {
        "id":     listing_id,
        "title":  title,
        "price":  price_str,
        "city":   city,
        "date":   date_str,
        "author": author,
        "url":    url,
    }


# ─────────────────────────────────────────────
#  DISCORD ALERTING
# ─────────────────────────────────────────────
def send_discord_alert(listing: dict) -> bool:
    """
    POSTs a rich Discord embed to the configured webhook URL.
    Returns True if the alert was delivered successfully.
    """
    if DISCORD_WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        log.warning("Discord webhook URL is not configured — skipping alert.")
        return False

    embed = {
        "title": listing["title"],
        "url": listing["url"],
        "color": 0xC8102E,   # Saudi red accent
        "thumbnail": {
            # Haraj favicon as thumbnail placeholder
            "url": "https://haraj.com.sa/favicon.ico"
        },
        "fields": [
            {
                "name": "💰 Price",
                "value": listing["price"],
                "inline": True,
            },
            {
                "name": "📍 City",
                "value": listing["city"],
                "inline": True,
            },
            {
                "name": "📅 Posted",
                "value": listing["date"],
                "inline": True,
            },
            {
                "name": "👤 Seller",
                "value": listing["author"],
                "inline": True,
            },
            {
                "name": "🔗 Listing",
                "value": listing["url"],
                "inline": False,
            },
        ],
        "footer": {
            "text": "Haraj Corvette Monitor • haraj.com.sa"
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    payload = {
        "username": "Haraj Monitor 🏎️",
        "avatar_url": "https://haraj.com.sa/favicon.ico",
        "embeds": [embed],
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
        # Discord returns 204 No Content on success
        if response.status_code in (200, 204):
            log.info("✅ Alert sent → %s", listing["title"])
            return True
        else:
            log.warning(
                "Discord webhook returned HTTP %s: %s",
                response.status_code,
                response.text[:200],
            )
            return False
    except requests.exceptions.RequestException as exc:
        log.error("Failed to send Discord alert: %s", exc)
        return False


# ─────────────────────────────────────────────
#  MAIN MONITORING LOOP
# ─────────────────────────────────────────────
def main() -> None:
    log.info("=" * 55)
    log.info("  Haraj Corvette Monitor — starting up")
    log.info("  Keyword : %s", SEARCH_KEYWORD)
    log.info("  State   : %s", STATE_FILE.resolve())
    log.info("  Proxies : %s", "Enabled" if PROXIES else "Disabled")
    log.info("  Webhook : %s", "Configured ✓" if DISCORD_WEBHOOK_URL != "YOUR_DISCORD_WEBHOOK_URL_HERE" else "⚠️  NOT SET")
    log.info("=" * 55)

    seen_ids = load_seen_ids()
    log.info("Loaded %d previously seen listing IDs.", len(seen_ids))

    log.info("─── Polling Haraj for '%s' ───", SEARCH_KEYWORD)

    raw_listings = fetch_listings(SEARCH_KEYWORD)
    log.info("Fetched %d listings from API.", len(raw_listings))

    new_count = 0
    for raw in raw_listings:
        listing = parse_listing(raw)
        if listing is None:
            continue

        if listing["id"] in seen_ids:
            continue   # Already alerted — skip

        # ── NEW listing found ──
        log.info(
            "🆕 New listing [%s]: %s | %s | %s",
            listing["id"],
            listing["title"],
            listing["price"],
            listing["city"],
        )
        send_discord_alert(listing)
        seen_ids.add(listing["id"])
        new_count += 1

    # Persist updated state regardless of whether new listings were found
    save_seen_ids(seen_ids)
    log.info(
        "Poll complete. %d new listing(s) found. Total seen: %d.",
        new_count,
        len(seen_ids),
    )


# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Interrupted by user. Exiting.")
