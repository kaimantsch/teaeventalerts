# Tea Event Web Page Change Watcher

Watches the [Bardo Tea events page](https://bardotea.com/collections/events) and pings me when it changes, so I can grab a class spot before it fills.

## How it works

1. A scheduled job fetches the events page every 30 minutes, around the clock.
2. The page's relevant content is hashed and compared to the last stored hash.
3. If the hash changed, a notification with the page URL is sent to my phone.
4. The new hash is saved for the next run.

The job runs in the cloud (GitHub Actions), so it works whether my laptop is on or off.

## Setup

1. Create a Telegram bot via [@BotFather](https://t.me/botfather), grab the token.
2. Message your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat ID.
3. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as GitHub Actions secrets.
4. Push the repo. The workflow runs on its schedule automatically.

## Files

- `watcher.py` — fetches the page, hashes it, sends a Telegram message on change.
- `.github/workflows/check.yml` — GitHub Actions cron schedule.
- `last_hash.txt` — committed by the workflow each run; this is the change-detection state.
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

Prints each event the watcher currently parses (title, price, sold-out status, URL), plus the current vs. stored hash. No Telegram token required, no hash file written. Use this to confirm the page selector still works and to compare against the stored state.
