"""Indeed (il.indeed.com) — direct HTML, best-effort only. Indeed runs
aggressive anti-bot protection (Cloudflare) and usually blocks datacenter
IPs such as GitHub runners; when blocked, this returns [] and the run
continues. Reliable Indeed coverage comes via the JSearch scraper."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import Job, make_session, polite_get

log = logging.getLogger("agent")

BASE = "https://il.indeed.com"
SEARCH = BASE + "/jobs?q={q}&fromage=1"

SOURCE = "indeed"


def fetch(queries: list[str], cfg: dict) -> list[Job]:
    delay = float(cfg["limits"].get("request_delay_seconds", 1.0))
    session = make_session()
    jobs: list[Job] = []

    for q in queries:
        resp = polite_get(session, SEARCH.format(q=quote(q)), delay=max(delay, 2.0))
        if resp is None:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.job_seen_beacon, td.resultContent")
        if not cards:
            log.info("indeed: no cards for %r (likely blocked)", q)
            continue
        for card in cards:
            job = _parse(card)
            if job:
                jobs.append(job)

    log.info("indeed: %d jobs from %d queries", len(jobs), len(queries))
    return jobs


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def _parse(card) -> Job | None:
    try:
        link = card.select_one("a[data-jk], h2.jobTitle a")
        title = _text(card.select_one("h2.jobTitle")) or _text(link)
        if not title:
            return None
        jk = link.get("data-jk", "") if link else ""
        url = f"{BASE}/viewjob?jk={jk}" if jk else BASE + (link.get("href", "") if link else "")
        company = _text(card.select_one("[data-testid='company-name'], .companyName"))
        location = _text(card.select_one("[data-testid='text-location'], .companyLocation"))
        return Job(
            title=title,
            company=company,
            location=location,
            url=url,
            source=SOURCE,
            native_id=jk,
        )
    except Exception as exc:
        log.info("indeed: failed to parse a card: %s", exc)
        return None
