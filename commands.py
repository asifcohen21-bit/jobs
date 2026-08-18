"""Telegram command processing — lets the owner toggle the filter mode
from the phone. Runs at the start of every agent run.

Commands (only messages from the configured chat_id are honored):
  /fulltime — disable the student/part-time filter (all matching roles)
  /student  — student/part-time positions only (default)
  /status   — current mode + last-run statistics
"""
from __future__ import annotations

import logging

from notifier import Notifier
from storage import Store

log = logging.getLogger("agent")

HELP = (
    "🤖 <b>סוכן המשרות שלך</b>\n"
    "/student — רק משרות סטודנט / חלקיות (ברירת מחדל)\n"
    "/fulltime — גם משרות מלאות (ללא סינון סטודנט)\n"
    "/status — מצב נוכחי וסטטיסטיקות הריצה האחרונה"
)


def process(notifier: Notifier, store: Store) -> str:
    """Reads pending Telegram updates, applies commands, returns active mode."""
    mode = store.state.get("mode", "student")
    offset = int(store.state.get("tg_offset", 0))

    for update in notifier.get_updates(offset):
        offset = max(offset, int(update.get("update_id", 0)) + 1)
        msg = update.get("message") or update.get("edited_message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        if chat_id != notifier.chat_id:
            continue
        text = (msg.get("text") or "").strip().lower()

        if text.startswith("/fulltime"):
            mode = "fulltime"
            notifier.send("✅ מצב הוחלף: <b>כל המשרות</b> (כולל משרות מלאות).\n"
                          "להחזרה: /student")
        elif text.startswith("/student"):
            mode = "student"
            notifier.send("✅ מצב הוחלף: <b>משרות סטודנט / חלקיות בלבד</b>.\n"
                          "למשרות מלאות: /fulltime")
        elif text.startswith("/status"):
            notifier.send(_status_text(store, mode))
        elif text.startswith("/start") or text.startswith("/help"):
            notifier.send(HELP)

    store.state["tg_offset"] = offset
    store.state["mode"] = mode
    return mode


def _status_text(store: Store, mode: str) -> str:
    mode_label = "משרות סטודנט / חלקיות" if mode == "student" else "כל המשרות"
    last = store.state.get("last_run") or {}
    if not last:
        return f"📊 מצב: <b>{mode_label}</b>\nעדיין לא הושלמה ריצה."
    sources = ", ".join(f"{k}: {v}" for k, v in (last.get("sources") or {}).items())
    return (
        f"📊 מצב: <b>{mode_label}</b>\n"
        f"🕐 ריצה אחרונה: {last.get('at', '?')}\n"
        f"🔎 נסרקו: {last.get('scanned', 0)} | עברו סינון: {last.get('passed', 0)} | "
        f"חדשות: {last.get('new', 0)} | נשלחו: {last.get('sent', 0)}\n"
        f"🌐 מקורות: {sources or '—'}\n"
        f"🗂 סה\"כ משרות במעקב: {len(store.seen)}"
    )
