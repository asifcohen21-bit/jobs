"""Free persistence: two JSON files in data/, committed back to the repo
by the GitHub Actions workflow after every run.

- seen_jobs.json : {job_key: first_seen ISO date}  (deduplication)
- state.json     : mode, telegram offset, per-source query rotation,
                   JSearch budget counters, last-run stats
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

log = logging.getLogger("agent")


class Store:
    def __init__(self, data_dir: str | Path):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.seen_path = self.dir / "seen_jobs.json"
        self.state_path = self.dir / "state.json"
        self.seen: dict[str, str] = _load(self.seen_path)
        self.state: dict = _load(self.state_path)

    def is_seen(self, key: str) -> bool:
        return key in self.seen

    def mark_seen(self, key: str) -> None:
        self.seen[key] = dt.date.today().isoformat()

    def prune(self, retention_days: int) -> None:
        cutoff = (dt.date.today() - dt.timedelta(days=retention_days)).isoformat()
        before = len(self.seen)
        self.seen = {k: v for k, v in self.seen.items() if v >= cutoff}
        if len(self.seen) != before:
            log.info("pruned %d old dedup entries", before - len(self.seen))

    def save(self) -> None:
        _dump(self.seen_path, self.seen)
        _dump(self.state_path, self.state)


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8") or "{}")
        except ValueError:
            log.warning("corrupt %s, starting fresh", path.name)
    return {}


def _dump(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
