"""AllJobs.co.il — HTML search results (best-effort; the site sometimes
serves an anti-bot page, in which case zero jobs are returned and the run
continues without it)."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import Job, make_session, polite_get

log = logging.getLogger("agent")

BASE = "https://www.alljobs.co.il"
SEARCH = BASE + "/SearchResultsGuest.aspx?page=1&freetxt={q}"

SOURCE = "alljobs"


def fetch(queries: list[str], cfg: dict) -> list[Job]:
    delay = float(cfg["limits"].get("request_delay_seconds", 1.0))
    session = make_session()
    jobs: list[Job] = []

    for q in queries:
        resp = polite_get(session, SEARCH.format(q=quote(q)), delay=max(delay, 1.5))
        if resp is None:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.job-content-top")
        if not cards:
            log.info("alljobs: no job cards for %r (possibly blocked)", q)
            continue
        for card in cards:
            job = _parse(card)
            if job:
                jobs.append(job)

    log.info("alljobs: %d jobs from %d queries", len(jobs), len(queries))
    return jobs


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def _parse(card) -> Job | None:
    try:
        title_link = card.select_one(".job-content-top-title a[href*='JobID=']")
        if not title_link:
            return None
        title = _text(title_link)
        href = title_link.get("href", "")
        m = re.search(r"JobID=(\d+)", href)
        native_id = m.group(1) if m else ""
        url = BASE + href if href.startswith("/") else href

        company = _text(card.select_one(".job-content-top-title .T14"))

        loc_box = card.select_one(".job-content-top-location")
        cities = [_text(a) for a in card.select(".job-regions-content a")]
        location = ", ".join(c for c in cities if c) or _text(loc_box)
        location = location.replace("מיקום המשרה:", "").strip()

        scope_parts = [_text(d) for d in card.select(".job-types-content div")]
        scope = ", ".join(p for p in scope_parts if p)
        if not scope:
            scope = _text(card.select_one(".job-content-top-type")).replace(
                "סוג משרה:", "").strip()

        description = _text(card.select_one(".job-content-top-desc"))[:2000]

        return Job(
            title=title,
            company=company or "חסוי",
            location=location,
            url=url,
            source=SOURCE,
            native_id=native_id,
            description=description,
            scope=scope,
        )
    except Exception as exc:
        log.info("alljobs: failed to parse a card: %s", exc)
        return None
