"""Job-board scrapers. Each module exposes fetch(queries, cfg) -> list[Job]
(jsearch also receives the persistent state for budget tracking)."""
from . import alljobs, drushim, glassdoor, indeed, jsearch, linkedin  # noqa: F401
from .base import Job, rotate  # noqa: F401
