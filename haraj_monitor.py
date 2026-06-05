"""
haraj_monitor.py
────────────────────────────────────────────────────────────────
Monitors Haraj (haraj.com.sa) for new C6 Corvette listings by
scraping the search results page and sends Discord Webhook alerts.

Requirements:
    pip install requests beautifulsoup4

Usage:
    1. Set DISCORD_WEBHOOK_URL below (or export as env variable).
    2. Optionally add proxies to the PROXIES dict.
    3. python haraj_monitor.py
────────────────────────────────────────────────────────────────
"""

import json
import os
import re
import logging
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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

# Haraj search page base URL
SEARCH_URL = "https://haraj.com.sa/search/"

# Listings whose title contains ANY of these words are skipped.
# Add or remove Arabic terms to tune what counts as a "non-car" listing.
EXCLUDE_KEYWORDS = [
    "رنج",       # rims / wheels
    "رنجات",     # rims (plural)
    "إطار",      # tire
    "اطار",      # tire (alternate spelling)
    "طارات",     # tires
    "عجل",       # wheel
    "عجلات",     # wheels
    "ملحقات",    # accessories
    "قطع غيار", # spare parts
    "قطعة",      # part
    "مقود",      # steering wheel
    "مقاعد",     # seats
    "مقعد",      # seat
    "مرايا",     # mirrors
    "مصابيح",    # lights / headlights
    "فانوس",     # headlight
    "كاميرا",    # camera
    "صدام",      # bumper
    "شنطة",      # trunk lid
    "كبوت",      # hood
    "باب",       # door
    "زجاج",      # glass
]

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
_proxy_url = os.environ.get("PROXY_URL", "")
PROXIES = {"http": _proxy_url, "https": _proxy_url} if _proxy_url else {}

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Google Chrome";v="125", "Chromium";v="125", "Not/A)Brand";v="8"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
}

# Regex patterns for parsing listing links from HTML
_LISTING_HREF_RE = re.compile(r"^/(\d{7,})/([^/?#]*)")
_CITY_HREF_RE    = re.compile(r"/cit(?:y|ies)/", re.IGNORECASE)
_USER_HREF_RE    = re.compile(r"/users?/", re.IGNORECASE)


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
#  HARAJ HTML SCRAPER  —  fetch listings
# ─────────────────────────────────────────────
def fetch_listings(keyword: str) -> list[dict]:
    """
    GETs the Haraj search results page and parses listing cards from the HTML.
    Returns a list of raw listing dicts. Returns an empty list on any failure.
    """
    url = SEARCH_URL + urllib.parse.quote(keyword)
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            proxies=PROXIES or None,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        log.error("Request timed out after %s seconds.", REQUEST_TIMEOUT)
        return []
    except requests.exceptions.RequestException as exc:
        log.error("Network error: %s", exc)
        return []

    log.info("Search page: HTTP %s, %d bytes", response.status_code, len(response.content))
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    seen_ids: set[str] = set()
    results = []

    for a_tag in soup.find_all("a", href=_LISTING_HREF_RE):
        href = a_tag.get("href", "")
        m = _LISTING_HREF_RE.match(href)
        if not m:
            continue
        listing_id, slug = m.group(1), m.group(2)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        # Title: link text, or fall back to decoding the URL slug
        title = a_tag.get_text(strip=True)
        if not title:
            title = urllib.parse.unquote(slug).replace("-", " ").strip() or "No title"

        # Walk up the DOM to find the card container (stop before a parent
        # that holds multiple listing links — that's a list, not a card)
        card = a_tag
        for _ in range(8):
            parent = card.parent
            if parent is None:
                break
            if len(parent.find_all("a", href=_LISTING_HREF_RE)) > 1:
                break
            card = parent

        city_a   = card.find("a", href=_CITY_HREF_RE)
        city     = city_a.get_text(strip=True) if city_a else "Unknown"

        user_a   = card.find("a", href=_USER_HREF_RE)
        author   = user_a.get_text(strip=True) if user_a else "Unknown"

        # Price: first text node that is purely numeric (≥3 digits)
        price = None
        for node in card.find_all(string=True):
            clean = node.strip().replace(",", "").replace("ريال", "").strip()
            if clean.isdigit() and len(clean) >= 3:
                price = clean
                break

        # Date: prefer <time datetime="..."> ISO value, else visible text
        time_el = card.find("time")
        if time_el:
            date = time_el.get("datetime") or time_el.get_text(strip=True)
        else:
            date = ""

        results.append({
            "id":         listing_id,
            "title":      title,
            "price":      price,
            "city":       city,
            "date":       date,
            "authorName": author,
        })

    return results


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
            # Unix timestamp (seconds)
            dt = datetime.utcfromtimestamp(int(date_raw))
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError, OSError):
            try:
                # ISO 8601 (from <time datetime="...">)
                dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            except (ValueError, TypeError):
                date_str = str(date_raw)  # relative text e.g. "قبل ٨ ساعات"
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
    log.info("Fetched %d listings from page.", len(raw_listings))

    # Filter out parts / accessories based on title keywords
    def is_car_listing(raw: dict) -> bool:
        title = (raw.get("title") or "").lower()
        for kw in EXCLUDE_KEYWORDS:
            if kw in title:
                log.debug("Skipping non-car listing ('%s'): matched '%s'", raw.get("title"), kw)
                return False
        return True

    car_listings = [r for r in raw_listings if is_car_listing(r)]
    log.info("%d listings remain after filtering out parts/accessories.", len(car_listings))

    new_count = 0
    for raw in car_listings:
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
