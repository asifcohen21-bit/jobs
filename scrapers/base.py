"""Shared building blocks for all job-board scrapers."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field

import requests

log = logging.getLogger("agent")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    source: str
    native_id: str = ""      # the board's own stable job id, if it has one
    description: str = ""
    scope: str = ""          # e.g. "משרה חלקית, משרה מלאה"
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stable dedup key: source + native id, or a content hash."""
        if self.native_id:
            return f"{self.source}:{self.native_id}"
        digest = hashlib.sha1(
            f"{self.title}|{self.company}|{self.location}".lower().encode("utf-8")
        ).hexdigest()
        return f"{self.source}:{digest}"

    @property
    def content_key(self) -> str:
        """Source-independent key — collapses the same ad reposted under
        different job ids or on different boards."""
        text = re.sub(r"\s+", " ", f"{self.title}|{self.company}".lower()).strip()
        return "content:" + hashlib.sha1(text.encode("utf-8")).hexdigest()


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return s


def polite_get(session: requests.Session, url: str, *, delay: float = 1.0,
               timeout: int = 25, **kwargs) -> requests.Response | None:
    """GET with a politeness delay; returns None instead of raising."""
    time.sleep(delay)
    try:
        resp = session.get(url, timeout=timeout, **kwargs)
        if resp.status_code != 200:
            log.info("GET %s -> HTTP %s", url.split("?")[0], resp.status_code)
            return None
        return resp
    except requests.RequestException as exc:
        log.info("GET %s failed: %s", url.split("?")[0], exc)
        return None


def rotate(items: list, offset: int, count: int) -> list:
    """Take `count` items starting at `offset`, wrapping around the list."""
    if not items:
        return []
    if count >= len(items):
        return list(items)
    start = offset % len(items)
    doubled = items + items
    return doubled[start:start + count]
