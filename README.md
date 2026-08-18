# 🎯 Student Job Agent

A fully automated, **100% free** agent that scans Israeli job boards every 30 minutes
for student / part-time positions in **Data & BI, PMO, QA & Automation, and
Industrial Engineering & Operations**, filters them to the **South and Center of
Israel** (remote/hybrid included), and sends every new match straight to
**Telegram** — no duplicates, ever.

## How it works

```
GitHub Actions (cron, every 30 min, free)
  └─ python main.py
       0. COMMANDS — reads your Telegram messages: /student /fulltime /status
       1. SCRAPE   — Drushim (JSON API) · LinkedIn (guest API) · AllJobs (HTML)
                     · JSearch free tier (Indeed + Glassdoor) · Indeed/Glassdoor direct (best-effort)
       2. FILTER   — student/part-time + role keywords + South/Center location (HE+EN) + remote/hybrid
       3. DEDUPE   — data/seen_jobs.json (committed back to this repo = free database)
       4. NOTIFY   — Telegram Bot API: title, company, location, direct link
```

## Setup (one time, ~10 minutes)

### 1. Create your Telegram bot
1. In Telegram, open **@BotFather** → send `/newbot` → pick a name and a username.
2. Copy the **token** it gives you (looks like `123456789:AAE...`).
3. Open a chat with your new bot and send it any message (e.g. `hi`).
4. Get your **chat id**: open in a browser
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   and copy the number at `"chat":{"id": ... }`.

### 2. Test locally (optional but recommended)
```
copy .env.example .env     # then edit .env with your token + chat id
pip install -r requirements.txt
python main.py --dry-run   # prints alerts instead of sending
python main.py             # real run — first run sends the 10 newest matches
```

### 3. Deploy to GitHub (free 24/7)
1. Create a **public** repository (public = unlimited free Actions minutes).
2. Push this project to it.
3. In the repo: **Settings → Secrets and variables → Actions → New repository secret**:
   - `TELEGRAM_BOT_TOKEN` — the token from BotFather
   - `TELEGRAM_CHAT_ID` — your chat id
   - `RAPIDAPI_KEY` — *(optional, see step 4)*
4. Go to the **Actions** tab → enable workflows → open **Student Job Agent** →
   **Run workflow** to test. You should get Telegram alerts within ~3 minutes.

That's it — it now runs every 30 minutes, forever, for free.

### 4. Optional: JSearch (limited value for Israel)
Indeed and Glassdoor block direct scraping. The **JSearch** API (RapidAPI,
free Basic plan, secret `RAPIDAPI_KEY`) was wired in as an aggregator, but
**Google for Jobs — its data source — has no Israel index**, so it returns
zero local Israeli positions (verified live). Leaving the secret unset is
fine: Drushim + LinkedIn + AllJobs cover the Israeli market, and Indeed's
Israeli listings are mostly cross-posts of the same inventory. The agent
budgets JSearch to ~6 requests/day if you do enable it.

## Telegram commands

| Command | Effect |
|---|---|
| `/student` | Student / part-time positions only (**default**) |
| `/fulltime` | Show **all** matching jobs, including full-time |
| `/status` | Current mode + last-run statistics |

Commands are picked up at the start of the next run (up to ~30 minutes).

## Tuning

Everything lives in **`config.yaml`** — search queries (Hebrew/English), role
keywords, excluded words, excluded companies, city whitelist (South/Center,
Hebrew + English), remote keywords, and rate limits. Edit, commit, push — the
next run uses the new rules.

## Notes & limitations

- GitHub's scheduler is best-effort: runs can occasionally be delayed ~5–15 min.
- Indeed/Glassdoor direct scrapers usually get blocked from cloud IPs — that's
  expected; JSearch is the reliable path for them.
- `data/seen_jobs.json` and `data/state.json` are updated by the workflow
  itself (that's the free "database" — and the commits keep the schedule from
  being auto-disabled for inactivity).
