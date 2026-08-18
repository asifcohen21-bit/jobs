"""Drushim.co.il — internal JSON search API used by their site (verified live)."""
from __future__ import annotations

import logging
from urllib.parse import quote

from .base import Job, make_session, polite_get

log = logging.getLogger("agent")

BASE = "https://www.drushim.co.il"
API = BASE + "/api/jobs/search?searchterm={q}&ssaen=1&page={page}"

SOURCE = "drushim"


def fetch(queries: list[str], cfg: dict) -> list[Job]:
    limits = cfg["limits"]
    pages = int(limits.get("drushim_pages_per_query", 2))
    delay = float(limits.get("request_delay_seconds", 1.0))
    session = make_session()
    jobs: list[Job] = []

    for q in queries:
        for page in range(1, pages + 1):
            resp = polite_get(session, API.format(q=quote(q), page=page), delay=delay)
            if resp is None:
                break
            try:
                data = resp.json()
            except ValueError:
                log.info("drushim: non-JSON response for %r", q)
                break
            results = data.get("ResultList") or []
            for item in results:
                job = _parse(item)
                if job:
                    jobs.append(job)
            total_pages = data.get("TotalPagesNumber") or 1
            if page >= total_pages:
                break

    log.info("drushim: %d jobs from %d queries", len(jobs), len(queries))
    return jobs


def _parse(item: dict) -> Job | None:
    try:
        content = item.get("JobContent") or {}
        info = item.get("JobInfo") or {}
        company = (item.get("Company") or {}).get("CompanyDisplayName") or ""
        title = content.get("Name") or ""
        if not title:
            return None

        regions = [r.get("NameInHebrew", "") for r in content.get("Regions") or []]
        zones = []
        for z in content.get("Zones") or []:
            zones.append(z.get("NameInHebrew", ""))
            zones.append(z.get("NameInEnglish", ""))
        location = ", ".join(x for x in regions + zones if x)

        scopes = ", ".join(
            s.get("NameInHebrew", "") for s in content.get("Scopes") or []
        )
        description = " ".join(
            x for x in (content.get("Description"), content.get("Requirements")) if x
        )

        link = info.get("Link") or ""
        code = item.get("Code") or content.get("JobCode") or ""
        url = BASE + link if link else f"{BASE}/job/{code}/"

        return Job(
            title=title.strip(),
            company=company.strip() or "חסוי",
            location=location,
            url=url,
            source=SOURCE,
            native_id=str(code),
            description=description,
            scope=scopes,
        )
    except Exception as exc:  # one bad record must not kill the run
        log.info("drushim: failed to parse a record: %s", exc)
        return None
