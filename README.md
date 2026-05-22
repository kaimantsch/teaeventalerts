# Tea Event Web Page Change Watcher

Watches the [Bardo Tea events page](https://bardotea.com/collections/events) and pings me when it changes, so I can grab a class spot before it fills.

## How it works

1. A scheduled job fetches the Bardo Tea events feed every 30 minutes, around the clock.
2. A signature of each event (title, link, sold-out status) is hashed and compared to the last stored hash.
3. If the hash changed, a notification with the page URL is sent to my phone.
4. The new hash is saved for the next run.

The job runs in the cloud (GitHub Actions), so it works whether my laptop is on or off.

A canary watches the watcher: if no successful fetch happens for 4 hours, a one-time Telegram alert fires so I notice silent breakage (URL change, sustained bot block, etc.).

### Why curl, and why the JSON feed

The site sits behind Cloudflare bot protection that blocks the Python HTTP
client by fingerprinting the request at the TLS layer (changing headers does
not help). The watcher fetches with `curl` instead, against Shopify's
structured products feed (`/collections/events/products.json`) rather than
scraping the HTML page. The feed is also cleaner to parse and not tied to a
fragile CSS selector. Telegram has no such protection, so notifications still
go out via the `requests` library.

## Setup

1. Create a Telegram bot via [@BotFather](https://t.me/botfather), grab the token.
2. Message your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat ID.
3. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as GitHub Actions secrets.
4. Push the repo. The workflow runs on its schedule automatically.

## Files

- `watcher.py` — fetches the events feed, hashes it, sends a Telegram message on change.
- `.github/workflows/check.yml` — GitHub Actions cron schedule.
- `last_hash.txt` — committed by the workflow on change; the page-hash baseline.
- `last_success.txt` — UTC timestamp of the most recent successful fetch (refreshed every ~2h to limit git noise). Powers the staleness canary.
- `last_canary.txt` — UTC timestamp of the most recent canary alert; used to dedupe one alert per outage.
- `REQUIREMENTS.md` — what this project does and doesn't do.
- `CLAUDE.md` — guidance for Claude Code when working on this project.

## Running locally

```bash
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python watcher.py
```

## Checking what the script sees

```bash
python watcher.py --list
```

Prints each event the watcher currently parses (title, price, sold-out status, URL), plus the current vs. stored hash. No Telegram token required, no hash file written. Use this to confirm the feed is reachable and to compare against the stored state.
