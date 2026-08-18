"""LinkedIn — public guest job-search endpoint (no login), verified live."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import Job, make_session, polite_get

log = logging.getLogger("agent")

API = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={q}&location=Israel&f_TPR=r86400&start=0"
)

SOURCE = "linkedin"


def fetch(queries: list[str], cfg: dict) -> list[Job]:
    delay = float(cfg["limits"].get("request_delay_seconds", 1.0))
    session = make_session()
    jobs: list[Job] = []

    for q in queries:
        resp = polite_get(session, API.format(q=quote(q)), delay=max(delay, 1.5))
        if resp is None or not resp.text.strip():
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("div.base-search-card"):
            job = _parse(card)
            if job:
                jobs.append(job)

    log.info("linkedin: %d jobs from %d queries", len(jobs), len(queries))
    return jobs


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def _parse(card) -> Job | None:
    try:
        title = _text(card.select_one(".base-search-card__title"))
        if not title:
            return None
        company = _text(card.select_one(".base-search-card__subtitle"))
        location = _text(card.select_one(".job-search-card__location"))

        urn = card.get("data-entity-urn", "")  # urn:li:jobPosting:4455263114
        native_id = urn.rsplit(":", 1)[-1] if urn else ""

        link_node = card.select_one("a.base-card__full-link")
        url = (link_node.get("href", "") if link_node else "").split("?")[0]
        if not url and native_id:
            url = f"https://www.linkedin.com/jobs/view/{native_id}/"

        return Job(
            title=title,
            company=company,
            location=location,
            url=url,
            source=SOURCE,
            native_id=native_id,
        )
    except Exception as exc:
        log.info("linkedin: failed to parse a card: %s", exc)
        return None
