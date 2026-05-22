#!/usr/bin/env python3
"""Watch the Bardo Tea events feed; ping Telegram when the listings change.

The site sits behind Cloudflare bot protection that blocks the Python HTTP
client at the TLS-fingerprint level. We fetch with `curl` (a standard tool,
present on the GitHub runner) against Shopify's structured products feed
instead of scraping HTML. Telegram has no such protection, so notifications
still go out via `requests`.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

SITE = "https://bardotea.com"
URL = f"{SITE}/collections/events"                      # human-facing page, used in notifications
API_URL = f"{SITE}/collections/events/products.json"    # structured feed we actually fetch
HASH_FILE = Path("last_hash.txt")
SUCCESS_FILE = Path("last_success.txt")
CANARY_FILE = Path("last_canary.txt")
STALENESS_THRESHOLD = timedelta(hours=4)     # alert if no successful fetch in this long
SUCCESS_WRITE_INTERVAL = timedelta(hours=2)  # only refresh last_success this often, to limit git noise
TIMEZONE = ZoneInfo("America/Los_Angeles")   # used only for diagnostic timestamps
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def curl_get(url: str) -> tuple[int, str]:
    """Fetch a URL with curl. Returns (http_status, body).
    Raises ConnectionError on a curl transport-level failure (network, DNS, TLS, timeout)."""
    try:
        result = subprocess.run(
            ["curl", "-sSL", "--compressed", "-A", USER_AGENT,
             "--max-time", "30", "-w", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=45,
        )
    except subprocess.TimeoutExpired:
        raise ConnectionError("curl timed out")
    if result.returncode != 0:
        raise ConnectionError(
            f"curl transport error (exit {result.returncode}): {result.stderr.strip()}"
        )
    body, _, status = result.stdout.rpartition("\n")
    try:
        return int(status), body
    except ValueError:
        raise ConnectionError(f"could not parse curl status from output tail: {status!r}")


def fetch_events_data() -> dict | None:
    """Fetch the Shopify events feed via curl, with one retry on transient failure.
    Returns parsed JSON, or None when giving up on a transient error.
    Raises on non-transient HTTP errors (e.g. 404) so the workflow fails loudly.

    Transient (soft-fail, retry next run): connection errors, timeouts, 5xx,
    429, 403. A 403 here is the Cloudflare bot challenge; it tends to be
    intermittent, and a sustained outage is caught by the staleness canary,
    so reding the build on every 403 would just be alarm fatigue."""
    last_err = None
    for attempt in (1, 2):
        status = None
        body = ""
        try:
            status, body = curl_get(API_URL)
        except ConnectionError as exc:
            last_err = str(exc)

        if status == 200:
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                last_err = "HTTP 200 but body was not JSON (likely a bot-check page)"
        elif status in (404, 410):
            raise RuntimeError(
                f"Events feed returned HTTP {status}; the URL may have changed. {API_URL}"
            )
        elif status is not None:
            last_err = f"HTTP {status}"  # 403 / 429 / 5xx: transient

        if attempt == 1:
            time.sleep(5)

    print(f"Transient fetch failure after retry: {last_err}. Will try again next run.")
    return None


def read_iso(path: Path) -> datetime | None:
    if not path.exists():
        return None
    raw = path.read_text().strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def write_iso(path: Path, dt: datetime) -> None:
    path.write_text(dt.isoformat() + "\n")


def maybe_send_canary(now: datetime) -> None:
    """Ping Telegram if we haven't had a successful fetch in STALENESS_THRESHOLD.
    Dedupes via last_canary.txt: one alert per stale episode."""
    last_success = read_iso(SUCCESS_FILE)
    if last_success is None:
        return  # no baseline yet, nothing to compare
    age = now - last_success
    if age < STALENESS_THRESHOLD:
        return
    last_canary = read_iso(CANARY_FILE)
    if last_canary is not None and last_canary > last_success:
        return  # already alerted for this outage
    hours = int(age.total_seconds() // 3600)
    send_telegram(
        f"Bardo Tea watcher: no successful fetch in ~{hours}h "
        f"(last success {last_success.isoformat(timespec='minutes')}). "
        "Check the GitHub Actions workflow."
    )
    write_iso(CANARY_FILE, now)
    print(f"Canary sent: stale by {hours}h.")


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


def extract_events(data: dict) -> list[dict]:
    """Pull a structured list of events from the Shopify feed."""
    events = []
    for product in data.get("products", []):
        variants = product.get("variants", [])
        available = any(v.get("available") for v in variants)
        price = variants[0].get("price") if variants else None
        events.append({
            "title": product.get("title", "(no title)"),
            "price": f"${price}" if price else "",
            "status": "AVAILABLE" if available else "SOLD OUT",
            "url": f"{SITE}/products/{product.get('handle', '')}",
        })
    return events


def extract_signature(data: dict) -> str:
    """Build a stable string capturing each event's identity and availability.
    Sorted so a reorder alone is not treated as a change; a new event, a
    removed event, or a sold-out/available flip all change the signature."""
    lines = [
        f"{ev['title']}|{ev['url']}|{ev['status']}"
        for ev in extract_events(data)
    ]
    return "\n".join(sorted(lines))


def run_list() -> int:
    """Diagnostic: fetch the feed, print events as the script sees them, plus hash state."""
    data = fetch_events_data()
    if data is None:
        print("Could not fetch the events feed (transient error). Try again shortly.")
        return 0

    new_hash = hashlib.sha256(extract_signature(data).encode("utf-8")).hexdigest()
    old_hash = HASH_FILE.read_text().strip() if HASH_FILE.exists() else ""
    events = extract_events(data)

    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    print(f"Bardo Tea events as of {now}")
    print(f"URL:           {URL}")
    print(f"Events found:  {len(events)}")
    print()
    if not events:
        print("(no events in feed — the feed format may have changed)")
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
    last_success = read_iso(SUCCESS_FILE)
    last_canary = read_iso(CANARY_FILE)
    print(f"Last success:  {last_success.isoformat(timespec='minutes') if last_success else '(none recorded)'}")
    if last_canary:
        print(f"Last canary:   {last_canary.isoformat(timespec='minutes')}")
    return 0


def main() -> int:
    now = datetime.now(timezone.utc)
    try:
        maybe_send_canary(now)
    except Exception as exc:
        # Canary is bonus monitoring; don't let it take the run down.
        print(f"Canary check failed (continuing): {exc}")

    data = fetch_events_data()
    if data is None:
        return 0

    last_success = read_iso(SUCCESS_FILE)
    if last_success is None or (now - last_success) >= SUCCESS_WRITE_INTERVAL:
        write_iso(SUCCESS_FILE, now)

    new_hash = hashlib.sha256(extract_signature(data).encode("utf-8")).hexdigest()
    old_hash = HASH_FILE.read_text().strip() if HASH_FILE.exists() else ""

    if new_hash == old_hash:
        print(f"No change ({new_hash[:12]}).")
        return 0

    HASH_FILE.write_text(new_hash + "\n")

    if not old_hash:
        print(f"Baseline recorded ({new_hash[:12]}). No notification on first run.")
        return 0

    send_telegram(f"Bardo Tea events page changed:\n{URL}")
    print("Change detected; notification sent.")
    return 0


if __name__ == "__main__":
    if "--list" in sys.argv[1:]:
        sys.exit(run_list())
    sys.exit(main())
