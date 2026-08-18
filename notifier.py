"""Telegram Bot API integration — sending alerts and reading commands."""
from __future__ import annotations

import html
import logging
import time

import requests

from scrapers.base import Job

log = logging.getLogger("agent")

API = "https://api.telegram.org/bot{token}/{method}"

SOURCE_LABELS = {
    "drushim": "Drushim",
    "linkedin": "LinkedIn",
    "alljobs": "AllJobs",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
}


class Notifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = str(chat_id)

    def _call(self, method: str, payload: dict) -> dict | None:
        try:
            resp = requests.post(
                API.format(token=self.token, method=method),
                json=payload, timeout=25,
            )
            data = resp.json()
            if not data.get("ok"):
                log.warning("telegram %s failed: %s", method, data.get("description"))
                return None
            return data
        except (requests.RequestException, ValueError) as exc:
            log.warning("telegram %s error: %s", method, exc)
            return None

    def send(self, text: str) -> bool:
        time.sleep(1.1)  # stay under Telegram's rate limit
        data = self._call("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        return data is not None

    def get_updates(self, offset: int) -> list[dict]:
        data = self._call("getUpdates", {"offset": offset, "timeout": 0})
        return data.get("result", []) if data else []


def format_job(job: Job, mode: str) -> str:
    source = SOURCE_LABELS.get(job.source, job.source)
    lines = [
        f"🎯 <b>{html.escape(job.title)}</b>",
        f"🏢 {html.escape(job.company or 'לא צוין')}",
        f"📍 {html.escape(job.location or 'לא צוין')}",
    ]
    if job.scope:
        lines.append(f"🕒 {html.escape(job.scope)}")
    lines.append(f"🌐 {html.escape(source)}")
    if job.url:
        lines.append(f'🔗 <a href="{html.escape(job.url, quote=True)}">למשרה המלאה</a>')
    return "\n".join(lines)
