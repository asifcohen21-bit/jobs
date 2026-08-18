"""Glassdoor — direct HTML, best-effort only. Glassdoor uses strong anti-bot
protection (DataDome) and generally blocks non-browser traffic; when blocked
this returns [] and the run continues. Reliable Glassdoor coverage comes via
the JSearch scraper. This parser reads the JSON-LD job listings embedded in
the search page when the page is served."""
from __future__ import annotations

import json
import logging
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import Job, make_session, polite_get

log = logging.getLogger("agent")

SEARCH = "https://www.glassdoor.com/Job/israel-{q}-jobs-SRCH_IL.0,6_IN119_KO7,999.htm"

SOURCE = "glassdoor"


def fetch(queries: list[str], cfg: dict) -> list[Job]:
    delay = float(cfg["limits"].get("request_delay_seconds", 1.0))
    session = make_session()
    jobs: list[Job] = []

    for q in queries:
        slug = quote(q.lower().replace(" ", "-"))
        resp = polite_get(session, SEARCH.format(q=slug), delay=max(delay, 2.0))
        if resp is None:
            continue
        found = _parse_jsonld(resp.text)
        if not found:
            log.info("glassdoor: no listings for %r (likely blocked)", q)
        jobs.extend(found)

    log.info("glassdoor: %d jobs from %d queries", len(jobs), len(queries))
    return jobs


def _parse_jsonld(html: str) -> list[Job]:
    jobs: list[Job] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(script.string or "")
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") == "ItemList":
                    items.extend(e.get("item", e) for e in item.get("itemListElement", [])
                                 if isinstance(e, dict))
                    continue
                if item.get("@type") != "JobPosting":
                    continue
                org = item.get("hiringOrganization") or {}
                loc = item.get("jobLocation") or {}
                if isinstance(loc, list):
                    loc = loc[0] if loc else {}
                addr = loc.get("address") or {}
                location = ", ".join(x for x in (
                    addr.get("addressLocality"), addr.get("addressRegion")) if x)
                jobs.append(Job(
                    title=item.get("title") or "",
                    company=org.get("name") or "" if isinstance(org, dict) else str(org),
                    location=location,
                    url=item.get("url") or "",
                    source=SOURCE,
                    description=(item.get("description") or "")[:2000],
                    scope=item.get("employmentType") or "",
                ))
    except Exception as exc:
        log.info("glassdoor: parse failed: %s", exc)
    return [j for j in jobs if j.title]
