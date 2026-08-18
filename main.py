"""Student Job Agent — one full cycle per invocation.

  commands -> scrape -> filter -> dedupe -> notify -> persist

Designed to be triggered every 30 minutes by GitHub Actions (see
.github/workflows/agent.yml). Run locally with --dry-run to test without
sending anything or touching the saved state.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
from pathlib import Path

import yaml

import commands
import filters
from notifier import Notifier, format_job
from scrapers import alljobs, drushim, glassdoor, indeed, jsearch, linkedin, rotate
from storage import Store

ROOT = Path(__file__).parent
log = logging.getLogger("agent")


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_dotenv() -> None:
    """Minimal .env loader for local runs (GitHub Actions injects real env)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def scrape_all(cfg: dict, store: Store) -> tuple[list, dict]:
    """Runs every scraper, isolating failures. Returns (jobs, per-source counts)."""
    queries = cfg["search_queries"]
    hebrew, english = queries["hebrew"], queries["english"]
    limits = cfg["limits"]
    rot = store.state.setdefault("rot", {})

    def take(name: str, items: list[str], count: int) -> list[str]:
        offset = int(rot.get(name, 0))
        rot[name] = offset + count
        return rotate(items, offset, count)

    plan = [
        ("drushim", lambda: drushim.fetch(queries.get("drushim", hebrew), cfg)),
        ("linkedin", lambda: linkedin.fetch(
            take("linkedin", english + hebrew,
                 int(limits.get("linkedin_queries_per_run", 10))), cfg)),
        ("alljobs", lambda: alljobs.fetch(
            take("alljobs", hebrew,
                 int(limits.get("alljobs_queries_per_run", 5))), cfg)),
        ("jsearch", lambda: jsearch.fetch(
            queries.get("jsearch", []), cfg, store.state)),
        ("indeed", lambda: indeed.fetch(
            take("indeed", english,
                 int(limits.get("besteffort_queries_per_run", 4))), cfg)),
        ("glassdoor", lambda: glassdoor.fetch(
            take("glassdoor", english,
                 int(limits.get("besteffort_queries_per_run", 4))), cfg)),
    ]

    jobs, counts = [], {}
    for name, fetch in plan:
        try:
            found = fetch()
        except Exception:
            log.exception("%s scraper crashed — continuing without it", name)
            found = []
        counts[name] = len(found)
        jobs.extend(found)

    # within-run dedup: by job id AND by title+company, so the same ad
    # reposted under several ids (or on several boards) arrives only once
    unique, seen_keys = [], set()
    for job in jobs:
        if job.key in seen_keys or job.content_key in seen_keys:
            continue
        seen_keys.add(job.key)
        seen_keys.add(job.content_key)
        unique.append(job)
    return unique, counts


def run(dry_run: bool) -> int:
    cfg = load_config()
    load_dotenv()
    store = Store(ROOT / "data")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    notifier = Notifier(token, chat_id) if token and chat_id else None
    if notifier is None and not dry_run:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing — "
                  "set them (or use --dry-run).")
        return 1

    # 0. commands — may flip the mode
    mode = store.state.get("mode", "student")
    if notifier and not dry_run:
        mode = commands.process(notifier, store)
    log.info("mode: %s", mode)

    # 1. scrape
    jobs, counts = scrape_all(cfg, store)
    log.info("scraped %d unique jobs %s", len(jobs), counts)

    # 2. filter
    job_filter = filters.JobFilter(cfg)
    passed = []
    for job in jobs:
        ok, reason = job_filter.passes(job, mode)
        if ok:
            passed.append(job)
        else:
            log.debug("filtered out [%s] %s — %s", job.source, job.title, reason)
    log.info("%d jobs passed filtering", len(passed))

    # 3. dedupe against history
    seeding = len(store.seen) == 0
    new_jobs = [j for j in passed
                if not (store.is_seen(j.key) or store.is_seen(j.content_key))]
    limits = cfg["limits"]
    cap = int(limits.get("seed_max_messages", 10)) if seeding \
        else int(limits.get("max_messages_per_run", 25))
    to_send = new_jobs[:cap]
    if seeding:
        log.info("first run — seeding %d jobs, alerting only the first %d",
                 len(new_jobs), len(to_send))

    # 4. notify
    def remember(job):
        store.mark_seen(job.key)
        store.mark_seen(job.content_key)

    sent = 0
    for job in to_send:
        message = format_job(job, mode)
        if dry_run:
            print("-" * 60)
            print(message)
            sent += 1
        elif notifier.send(message):
            remember(job)
            sent += 1
    if seeding and not dry_run:
        for job in new_jobs:  # swallow the backlog so it never floods
            remember(job)

    # 5. persist
    store.state["last_run"] = {
        "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "mode": mode,
        "scanned": len(jobs),
        "passed": len(passed),
        "new": len(new_jobs),
        "sent": sent,
        "sources": counts,
    }
    store.prune(int(limits.get("seen_retention_days", 60)))
    if not dry_run:
        store.save()

    log.info("done: scanned=%d passed=%d new=%d sent=%d seen_total=%d",
             len(jobs), len(passed), len(new_jobs), sent, len(store.seen))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Student job agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="print alerts instead of sending; do not save state")
    parser.add_argument("--verbose", action="store_true",
                        help="also log every filtered-out job with the reason")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
