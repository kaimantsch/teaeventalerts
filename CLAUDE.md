# Guidance for Claude Code

## What this project is

A single-purpose scheduled job that watches one URL and texts the owner when it changes. See `REQUIREMENTS.md` for the full spec.

## Hard constraints

- **Stay small.** The whole project should fit in a handful of files. If a change adds a framework, ORM, queue, or background-worker abstraction, push back — that's almost certainly the wrong shape.
- **No LLM calls in the runtime path.** Change detection is a plain hash compare. There is no scenario where the watcher should call an LLM API.
- **Zero recurring cost.** Don't introduce paid services (Twilio, hosted databases, paid monitoring). GitHub Actions + Telegram Bot API are both free at this volume.
- **Run in CI, not on the user's laptop.** Solutions that depend on the laptop being awake (cron on macOS, a long-running local script) defeat the point.
- **Idempotent.** Running twice in a row with no page change must not double-notify.

## Architecture in one paragraph

GitHub Actions cron triggers a Python script every hour, around the clock. The script fetches the events page, hashes the relevant content, compares to `last_hash.txt`, and on mismatch posts a message to a Telegram chat via the Bot API. The workflow then commits the new hash back to the repo. State lives in git; no database.

## Conventions

- One Python file (`watcher.py`). Don't split into modules until there's a real reason.
- Secrets are read from environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Never commit them.
- `last_hash.txt` is committed by the workflow on change. The first run after deploy records a baseline silently (no notification on empty prior hash) — that's intentional, not a bug.
- The watcher runs every hour around the clock. There used to be a Pacific-daylight gate; it was removed because the teachers post from overseas and drops can land at any hour.

## When extending

Before adding anything, check `REQUIREMENTS.md` § "Non-goals." Many obvious next steps (auto-register, diff what changed, multi-user) are explicitly out of scope. Ask the user before crossing those lines.
