#!/usr/bin/env python3
"""Watch the Bardo Tea events page; ping Telegram when the listings change."""
import hashlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://bardotea.com/collections/events"
SELECTOR = ".product-list-container"
HASH_FILE = Path("last_hash.txt")
TIMEZONE = ZoneInfo("America/Los_Angeles")  # used only for diagnostic timestamps
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def fetch_page() -> requests.Response | None:
    """Fetch the events page with one retry on transient failure. Returns None on giving up."""
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            response = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_err = exc
            if attempt == 1:
                time.sleep(5)
    print(f"Fetch failed after retry: {last_err}. Treating as transient; will try again next run.")
    return None


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = [name for name, val in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id)) if not val]
    if missing:
        raise RuntimeError(
            f"Telegram secret(s) not set or empty: {', '.join(missing)}. "
            "Check repo Settings → Secrets and variables → Actions."
        )
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


def extract_events(html: str) -> list[dict]:
    """Pull a structured list of events from the page for the --list diagnostic."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for block in soup.select(f"{SELECTOR} .product-block"):
        title_el = block.select_one(".title")
        price_el = block.select_one(".price")
        link_el = block.select_one("a.caption[href]") or block.select_one("a[href*='/products/']")
        sold_out = "sold-out" in (block.get("class") or []) or block.select_one(".product-label.unavailable") is not None
        events.append({
            "title": title_el.get_text(strip=True) if title_el else "(no title)",
            "price": " ".join(price_el.get_text(" ", strip=True).split()) if price_el else "",
            "status": "SOLD OUT" if sold_out else "AVAILABLE",
            "url": urljoin(URL, link_el["href"]) if link_el else "",
        })
    return events


def run_list() -> int:
    """Diagnostic: fetch the page, print events as the script sees them, plus hash state."""
    response = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    mode, content = extract_signature(response.text)
    new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    old_hash = HASH_FILE.read_text().strip() if HASH_FILE.exists() else ""

    events = extract_events(response.text)
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    print(f"Bardo Tea events as of {now}")
    print(f"URL:           {URL}")
    print(f"Signature mode: {mode}")
    print(f"Events found:  {len(events)}")
    print()
    if not events:
        print("(no event blocks parsed — selector may have broken)")
    for i, ev in enumerate(events, 1):
        print(f"{i}. [{ev['status']}] {ev['title']}")
        if ev["price"]:
            print(f"   Price: {ev['price']}")
        if ev["url"]:
            print(f"   URL:   {ev['url']}")
    print()
    print(f"Current hash:  {new_hash}")
    print(f"Stored hash:   {old_hash or '(none)'}")
    if not old_hash:
        print("State:         no baseline yet")
    elif new_hash == old_hash:
        print("State:         unchanged since last run")
    else:
        print("State:         CHANGED since last stored hash")
    return 0


def main() -> int:
    response = fetch_page()
    if response is None:
        return 0

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
    if "--list" in sys.argv[1:]:
        sys.exit(run_list())
    sys.exit(main())
