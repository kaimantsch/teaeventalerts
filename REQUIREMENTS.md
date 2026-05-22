# Requirements

## Goal

Get notified the moment Bardo Tea posts a new class so I can register before the small classes fill up.

## Functional requirements

1. **Target page**: `https://bardotea.com/collections/events`. The site is behind Cloudflare bot protection, so the watcher fetches the Shopify JSON feed (`/collections/events/products.json`) with `curl` rather than scraping the HTML page.
2. **Check frequency**: every 30 minutes, around the clock. The teachers post from overseas, so a daylight gate (Pacific) would miss drops.
3. **Change detection**: hash a signature of the event listings (title, link, sold-out status) and compare to the last saved hash.
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
- Authenticating to the site. Browser-impersonation tooling that exists specifically to defeat bot protection (`curl_cffi`, `cloudscraper`, headless browsers) also stays out. Fetching the public JSON feed with plain `curl` is allowed; if the site hard-blocks that too, revisit with the user rather than escalating.

## Open questions for the user

- Confirm Telegram is the right notification channel (vs. SMS or Signal).

## Architecture decision

**GitHub Actions cron + Python script + Telegram Bot API + hash committed back to repo.**

| Concern | Choice | Why |
|---|---|---|
| Scheduler | GitHub Actions cron | Free, runs without my laptop, no server to maintain. |
| Language | Python | `requests` + `hashlib` is enough; widely understood. |
| Storage | Committed `last_hash.txt` | No database needed; git history doubles as an audit log of changes. |
| Notification | Telegram Bot | Free, no carrier or SMS account; one HTTP POST. |
