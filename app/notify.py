from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite

from .config import (
    DB_PATH,
    EVENING_DIGEST_HOUR,
    MORNING_DUE_HOUR,
    NOTIFY_TZ,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_PROXY,
)
from .db import utcnow
from .due_utils import due_at_present, is_task_overdue, parse_task_dt
from .remind_utils import hourly_dedupe_key, in_hour_fire_window, next_hour_boundary_iso

log = logging.getLogger("notetask.notify")


TZ = ZoneInfo(NOTIFY_TZ)


def _now_local() -> datetime:
    return datetime.now(TZ)


async def _already_sent(db: aiosqlite.Connection, kind: str, dedupe_key: str) -> bool:
    cur = await db.execute(
        "SELECT 1 FROM notification_log WHERE kind=? AND dedupe_key=? LIMIT 1",
        (kind, dedupe_key),
    )
    return await cur.fetchone() is not None


async def _mark_sent(
    db: aiosqlite.Connection,
    kind: str,
    dedupe_key: str,
    task_id: int | None,
    title: str,
    body: str,
) -> None:
    now = utcnow()
    await db.execute(
        "INSERT OR IGNORE INTO notification_log(kind, dedupe_key, task_id, sent_at) VALUES(?,?,?,?)",
        (kind, dedupe_key, task_id, now),
    )
    await db.execute(
        """
        INSERT INTO app_notifications(created_at, kind, task_id, title, body, read_at)
        VALUES(?,?,?,?,?,NULL)
        """,
        (now, kind, task_id, title, body),
    )
    await db.commit()


def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode()
    handlers: list[urllib.request.BaseHandler] = []
    if TELEGRAM_PROXY:
        handlers.append(
            urllib.request.ProxyHandler({"http": TELEGRAM_PROXY, "https": TELEGRAM_PROXY})
        )
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with opener.open(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode())
            return bool(payload.get("ok"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Telegram send failed: %s", exc)
        return False


async def _deliver(
    db: aiosqlite.Connection,
    *,
    kind: str,
    dedupe_key: str,
    task_id: int | None,
    title: str,
    body: str,
    tg_text: str,
) -> None:
    if await _already_sent(db, kind, dedupe_key):
        return
    await _mark_sent(db, kind, dedupe_key, task_id, title, body)
    ok = await asyncio.to_thread(send_telegram, tg_text)
    if not ok:
        log.warning("Telegram delivery failed for %s", dedupe_key)


async def tick_once() -> None:
    now = _now_local()
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        cur = await db.execute(
            """
            SELECT id, title, due_at, remind_at, remind_rule, status
            FROM tasks
            WHERE deleted_at IS NULL AND status='open' AND kind='task'
            """
        )
        tasks = [dict(r) for r in await cur.fetchall()]

        for task in tasks:
            if (task.get("remind_rule") or "").strip().lower() == "hourly":
                if in_hour_fire_window(now):
                    key = hourly_dedupe_key(task["id"], now)
                    title = "Напоминание · каждый час"
                    body = task["title"]
                    await _deliver(
                        db,
                        kind="remind",
                        dedupe_key=key,
                        task_id=task["id"],
                        title=title,
                        body=body,
                        tg_text=f"⏰ {title}: {body}",
                    )
                    nxt = next_hour_boundary_iso(now + timedelta(minutes=1))
                    await db.execute(
                        "UPDATE tasks SET remind_at=?, updated_at=? WHERE id=?",
                        (nxt, utcnow(), task["id"]),
                    )
                    await db.commit()
            else:
                remind_dt = parse_task_dt(task.get("remind_at"))
                if remind_dt and remind_dt <= now <= remind_dt + timedelta(minutes=5):
                    key = f"remind:{task['id']}:{task.get('remind_at')}"
                    title = "Напоминание"
                    body = task["title"]
                    await _deliver(
                        db,
                        kind="remind",
                        dedupe_key=key,
                        task_id=task["id"],
                        title=title,
                        body=body,
                        tg_text=f"⏰ {title}: {body}",
                    )

            due_raw = task.get("due_at")
            if not due_at_present(due_raw):
                continue
            due_dt = parse_task_dt(due_raw)
            if not due_dt:
                continue
            has_time = bool(due_raw and "T" in due_raw)
            if has_time:
                if due_dt <= now <= due_dt + timedelta(minutes=5):
                    key = f"due:{task['id']}:{due_raw}"
                    title = "Срок задачи"
                    body = task["title"]
                    await _deliver(
                        db,
                        kind="due",
                        dedupe_key=key,
                        task_id=task["id"],
                        title=title,
                        body=body,
                        tg_text=f"📌 {title}: {body}",
                    )
            else:
                if (
                    due_dt.date() == now.date()
                    and now.hour >= MORNING_DUE_HOUR
                    and now <= due_dt.replace(hour=MORNING_DUE_HOUR, minute=5)
                ):
                    key = f"due_day:{task['id']}:{due_raw[:10]}"
                    title = "Срок сегодня"
                    body = task["title"]
                    await _deliver(
                        db,
                        kind="due",
                        dedupe_key=key,
                        task_id=task["id"],
                        title=title,
                        body=body,
                        tg_text=f"📌 Сегодня: {body}",
                    )

        if now.hour == EVENING_DIGEST_HOUR and now.minute < 2:
            digest_key = f"overdue_digest:{now.date().isoformat()}"
            if not await _already_sent(db, "overdue_digest", digest_key):
                today_key = now.date().isoformat()
                cur = await db.execute(
                    """
                    SELECT id, title, due_at
                    FROM tasks
                    WHERE deleted_at IS NULL AND status='open' AND kind='task'
                      AND due_at IS NOT NULL AND TRIM(due_at) != ''
                      AND SUBSTR(due_at, 1, 10) < ?
                    ORDER BY due_at, id
                    """,
                    (today_key,),
                )
                overdue = [dict(r) for r in await cur.fetchall()]
                overdue = [t for t in overdue if is_task_overdue(t.get("due_at"), now)]
                if overdue:
                    lines = [f"• {t['title']}" for t in overdue[:30]]
                    more = "" if len(overdue) <= 30 else f"\n…и ещё {len(overdue) - 30}"
                    body = "\n".join(lines) + more
                    title = f"Просрочено: {len(overdue)}"
                    await _deliver(
                        db,
                        kind="overdue_digest",
                        dedupe_key=digest_key,
                        task_id=None,
                        title=title,
                        body=body,
                        tg_text=f"⚠️ {title}\n{body}",
                    )
                else:
                    await db.execute(
                        "INSERT OR IGNORE INTO notification_log(kind, dedupe_key, task_id, sent_at) VALUES(?,?,?,?)",
                        ("overdue_digest", digest_key, None, utcnow()),
                    )
                    await db.commit()
    finally:
        await db.close()


async def notify_loop(stop: asyncio.Event) -> None:
    log.info(
        "Notify loop start tz=%s proxy=%s tg=%s",
        NOTIFY_TZ,
        bool(TELEGRAM_PROXY),
        bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
    )
    while not stop.is_set():
        try:
            await tick_once()
        except Exception:
            log.exception("Notify tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass
