"""JSearch (RapidAPI free tier) — aggregates Google for Jobs, which carries
Indeed and Glassdoor postings. Strictly budget-guarded so it never exceeds
the free monthly quota. Skipped entirely when RAPIDAPI_KEY is not set."""
from __future__ import annotations

import datetime as dt
import logging
import os

import requests

from .base import Job, USER_AGENT, rotate

log = logging.getLogger("agent")

API = "https://jsearch.p.rapidapi.com/search"
SOURCE = "jsearch"


def fetch(queries: list[str], cfg: dict, state: dict) -> list[Job]:
    api_key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not api_key:
        log.info("jsearch: no RAPIDAPI_KEY configured, skipping")
        return []

    limits = cfg["limits"]
    budget = int(limits.get("jsearch_monthly_budget", 180))
    per_slot = int(limits.get("jsearch_queries_per_slot", 2))
    slot_hours = limits.get("jsearch_slot_hours_utc", [5, 10, 15])

    now = dt.datetime.now(dt.timezone.utc)
    js = state.setdefault("jsearch", {})

    # monthly budget reset
    month = now.strftime("%Y-%m")
    if js.get("month") != month:
        js["month"] = month
        js["used"] = 0

    if js.get("used", 0) >= budget:
        log.info("jsearch: monthly budget exhausted (%s used)", js.get("used"))
        return []

    # run only once per daily slot (keeps usage at ~len(slots)*per_slot/day)
    slot = None
    for h in sorted(slot_hours):
        if now.hour >= h:
            slot = f"{now.date()}:{h}"
    if slot is None or js.get("last_slot") == slot:
        log.info("jsearch: not an active slot, skipping")
        return []

    picked = rotate(queries, js.get("qidx", 0), per_slot)
    js["qidx"] = js.get("qidx", 0) + per_slot
    js["last_slot"] = slot

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        "User-Agent": USER_AGENT,
    }
    jobs: list[Job] = []
    for q in picked:
        params = {
            "query": f"{q} in Israel",
            "country": "il",
            "date_posted": "today",
            "page": "1",
            "num_pages": "1",
        }
        js["used"] = js.get("used", 0) + 1
        try:
            resp = requests.get(API, headers=headers, params=params, timeout=25)
            if resp.status_code != 200:
                log.info("jsearch: HTTP %s for %r", resp.status_code, q)
                continue
            for item in resp.json().get("data") or []:
                job = _parse(item)
                if job:
                    jobs.append(job)
        except (requests.RequestException, ValueError) as exc:
            log.info("jsearch: request failed for %r: %s", q, exc)

    log.info("jsearch: %d jobs, budget used %d/%d", len(jobs), js["used"], budget)
    return jobs


def _parse(item: dict) -> Job | None:
    try:
        title = item.get("job_title") or ""
        if not title:
            return None
        city = item.get("job_city") or ""
        area = item.get("job_state") or ""
        location = ", ".join(x for x in (city, area) if x)
        if item.get("job_is_remote"):
            location = (location + ", Remote").strip(", ")
        scope = item.get("job_employment_type") or ""  # FULLTIME / PARTTIME
        if scope.upper() == "PARTTIME":
            scope = "part time"
        publisher = item.get("job_publisher") or ""
        return Job(
            title=title,
            company=item.get("employer_name") or "",
            location=location or "Israel",
            url=item.get("job_apply_link") or "",
            source=f"{SOURCE}({publisher})" if publisher else SOURCE,
            native_id=item.get("job_id") or "",
            description=(item.get("job_description") or "")[:2000],
            scope=scope,
        )
    except Exception as exc:
        log.info("jsearch: failed to parse a record: %s", exc)
        return None
