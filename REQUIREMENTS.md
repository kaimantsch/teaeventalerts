# Requirements

## Goal

Get notified the moment Bardo Tea posts a new class so I can register before the small classes fill up.

## Functional requirements

1. **Target page**: `https://bardotea.com/collections/events`
2. **Check frequency**: once per hour, during daylight hours only.
   - *Working definition of daylight:* 6:00 AM – 9:00 PM Pacific Time. Adjust if needed.
3. **Change detection**: hash the relevant portion of the page (event listings, not full HTML chrome that may rotate per request) and compare to the last saved hash.
4. **Notification**: when the hash changes, send a message containing the events page URL to my phone.
   - *Chosen channel:* Telegram (free, simple, no SMS gateway costs). SMS via Twilio and Signal via signal-cli are alternatives if Telegram doesn't suit.
5. **Persistence**: the last-seen hash must survive between runs.
6. **Hosting**: must run regardless of whether my laptop is on or off → cloud-hosted scheduled job.

## Non-functional requirements

- **Simplicity over completeness.** A single ~50-line script is better than a framework.
- **Minimal token / API usage.** No LLM calls; change detection is a plain hash compare.
- **Zero ongoing cost.** GitHub Actions free tier + Telegram Bot API are both free at this volume.
- **Low maintenance.** Should run untouched for months.

## Non-goals

- Auto-registering for the class. Notification only — I'll click the link and register myself.
- Diffing exactly *what* changed. Just "something changed, go look."
- Handling multiple sites or multiple users.
- Authenticating to the site or bypassing bot protection.

## Open questions for the user

- Confirm Telegram is the right notification channel (vs. SMS or Signal).
- Confirm the daylight window (6 AM – 9 PM Pacific) — adjust if your timezone or sleep schedule differs.
- Should we ignore changes that are clearly not new events (e.g. footer copy, tracking tokens in URLs)? If yes, we'll need a CSS selector for the events list.

## Architecture decision

**GitHub Actions cron + Python script + Telegram Bot API + hash committed back to repo.**

| Concern | Choice | Why |
|---|---|---|
| Scheduler | GitHub Actions cron | Free, runs without my laptop, no server to maintain. |
| Language | Python | `requests` + `hashlib` is enough; widely understood. |
| Storage | Committed `last_hash.txt` | No database needed; git history doubles as an audit log of changes. |
| Notification | Telegram Bot | Free, no carrier or SMS account; one HTTP POST. |
