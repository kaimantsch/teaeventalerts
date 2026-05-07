#!/usr/bin/env python3
"""Watch the Bardo Tea events page; ping Telegram when the listings change."""
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://bardotea.com/collections/events"
SELECTOR = ".product-list-container"
HASH_FILE = Path("last_hash.txt")
TIMEZONE = ZoneInfo("America/Los_Angeles")
DAYLIGHT_START = 6   # 6 AM Pacific, inclusive
DAYLIGHT_END = 22    # 10 PM Pacific, exclusive
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def in_daylight_window() -> bool:
    return DAYLIGHT_START <= datetime.now(TIMEZONE).hour < DAYLIGHT_END


def send_telegram(message: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=15,
    )
    response.raise_for_status()


def extract_signature(html: str) -> tuple[str, str]:
    """Return (mode, normalized_text). mode is 'targeted' or 'fallback'."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(SELECTOR)
    if container:
        text = " ".join(container.get_text(separator=" ", strip=True).split())
        if text:
            return "targeted", text
    body = soup.body or soup
    text = " ".join(body.get_text(separator=" ", strip=True).split())
    return "fallback", text


def main() -> int:
    if not in_daylight_window():
        print("Outside daylight window; skipping.")
        return 0

    response = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    mode, content = extract_signature(response.text)
    new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    old_hash = HASH_FILE.read_text().strip() if HASH_FILE.exists() else ""

    if new_hash == old_hash:
        print(f"No change ({mode}, {new_hash[:12]}).")
        return 0

    HASH_FILE.write_text(new_hash + "\n")

    if not old_hash:
        print(f"Baseline recorded ({mode}, {new_hash[:12]}). No notification on first run.")
        return 0

    prefix = "" if mode == "targeted" else "Selector failed; alerting on full-page change. "
    send_telegram(f"{prefix}Bardo Tea events page changed:\n{URL}")
    print(f"Change detected ({mode}); notification sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
