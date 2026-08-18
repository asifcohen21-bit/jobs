"""Mode-aware job filtering: role match, student/part-time, location, excludes.

Matching notes:
- Text and terms are normalized (lowercased, apostrophes stripped, hyphens
  and slashes become spaces) so "Part-Time" == "part time" and
  "Be'er Sheva" == "Beer Sheva".
- Terms match on word boundaries. The boundary check is ASCII-only on the
  left so Hebrew prefix letters still match: "בבאר שבע" matches "באר שבע",
  "הדרום" matches "דרום" — while "database" does NOT match "data".
"""
from __future__ import annotations

import re

from scrapers.base import Job


def _norm(text: str) -> str:
    text = (text or "").lower()
    for ch in "'’`׳":
        text = text.replace(ch, "")
    for ch in "-_/|":
        text = text.replace(ch, " ")
    return re.sub(r"\s+", " ", text).strip()


def _compile(terms: list[str]) -> re.Pattern:
    parts = [re.escape(_norm(t)) for t in terms if _norm(t)]
    pattern = r"(?<![A-Za-z0-9_])(?:%s)(?!\w)" % "|".join(parts)
    return re.compile(pattern)


class JobFilter:
    def __init__(self, cfg: dict):
        loc = cfg["locations"]
        self.role = _compile(cfg["role_words"])
        self.student = _compile(cfg["student_words"])
        self.parttime = _compile(cfg["parttime_words"])
        self.exclude = _compile(cfg["exclude_words"])
        self.location = _compile(
            list(loc.get("south", [])) + list(loc.get("center", []))
            + list(loc.get("region_words", []))
        )
        self.remote = _compile(cfg["remote_words"])
        companies = cfg.get("exclude_companies") or []
        self.exclude_companies = _compile(companies) if companies else None

    def passes(self, job: Job, mode: str) -> tuple[bool, str]:
        """Returns (passed, reason). mode: 'student' or 'fulltime'."""
        title = _norm(job.title)
        desc = _norm(job.description)
        scope = _norm(job.scope)
        location = _norm(job.location)
        everything = " | ".join((title, desc, scope, location))

        if self.exclude.search(title):
            return False, "excluded word in title"

        if self.exclude_companies and self.exclude_companies.search(_norm(job.company)):
            return False, "excluded company"

        if not self.role.search(title):
            return False, "no role word in title"

        if mode == "student":
            is_student = bool(
                self.student.search(title) or self.student.search(desc)
                or self.student.search(scope)
            )
            is_parttime = bool(
                self.parttime.search(title) or self.parttime.search(desc)
                or self.parttime.search(scope)
            )
            if not (is_student or is_parttime):
                return False, "not a student/part-time position"

        if not (self.location.search(location) or self.remote.search(everything)):
            return False, f"location not in South/Center ({job.location or 'unknown'})"

        return True, "ok"
