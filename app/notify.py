from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any
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
from .inbox_core import create_item_from_text
from .due_utils import due_at_present, is_task_overdue, parse_task_dt
from .remind_utils import hourly_dedupe_key, hourly_ready, in_hour_fire_window, next_hour_boundary_iso
from .task_complete import complete_task_row
from .tg_callbacks import parse_done_callback_data

log = logging.getLogger("notetask.notify")

TZ = ZoneInfo(NOTIFY_TZ)

# Wired from main at startup to avoid circular imports.
_normalize_repeat_rule = None
_next_due_from_rule = None


def configure_complete_helpers(
    normalize_repeat_rule,
    next_due_from_rule,
) -> None:
    global _normalize_repeat_rule, _next_due_from_rule
    _normalize_repeat_rule = normalize_repeat_rule
    _next_due_from_rule = next_due_from_rule


def _now_local() -> datetime:
    return datetime.now(TZ)


def _tg_opener() -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = []
    if TELEGRAM_PROXY:
        handlers.append(
            urllib.request.ProxyHandler({"http": TELEGRAM_PROXY, "https": TELEGRAM_PROXY})
        )
    return urllib.request.build_opener(*handlers)


def tg_api(method: str, payload: dict[str, Any], *, timeout: float = 25) -> dict[str, Any] | None:
    if not TELEGRAM_BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with _tg_opener().open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Telegram %s failed: %s", method, exc)
        return None


def send_telegram(
    text: str,
    *,
    task_id: int | None = None,
    with_complete: bool = False,
) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return False
    payload: dict[str, Any] = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if with_complete and task_id is not None:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": "✅ Выполнить", "callback_data": f"done:{task_id}"}]
            ]
        }
    result = tg_api("sendMessage", payload, timeout=20)
    return bool(result and result.get("ok"))


def answer_callback(callback_id: str, text: str, *, show_alert: bool = False) -> None:
    tg_api(
        "answerCallbackQuery",
        {"callback_query_id": callback_id, "text": text, "show_alert": show_alert},
        timeout=10,
    )


def edit_message_text(chat_id: int | str, message_id: int, text: str) -> None:
    tg_api(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=10,
    )


def parse_done_callback(data: str | None) -> int | None:
    return parse_done_callback_data(data)


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
    with_complete = kind in ("remind", "due") and task_id is not None
    ok = await asyncio.to_thread(
        send_telegram,
        tg_text,
        task_id=task_id,
        with_complete=with_complete,
    )
    if not ok:
        log.warning("Telegram delivery failed for %s", dedupe_key)


async def handle_callback_query(update: dict[str, Any]) -> None:
    cb = update.get("callback_query") or {}
    callback_id = str(cb.get("id") or "")
    data = cb.get("data")
    msg = cb.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    from_user = cb.get("from") or {}
    if str(chat_id) != str(TELEGRAM_CHAT_ID) and str(from_user.get("id")) != str(TELEGRAM_CHAT_ID):
        if callback_id:
            answer_callback(callback_id, "Нет доступа", show_alert=True)
        return
    task_id = parse_done_callback(data)
    if task_id is None:
        if callback_id:
            answer_callback(callback_id, "Неизвестная кнопка")
        return
    if _normalize_repeat_rule is None or _next_due_from_rule is None:
        if callback_id:
            answer_callback(callback_id, "Сервер не готов", show_alert=True)
        return

    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        result = await complete_task_row(
            db,
            task_id,
            normalize_repeat_rule=_normalize_repeat_rule,
            next_due_from_rule=_next_due_from_rule,
        )
    finally:
        await db.close()

    if not result:
        answer_callback(callback_id, "Задача не найдена", show_alert=True)
        return

    title = result.get("title") or f"#{task_id}"
    if result.get("rescheduled"):
        note = f"✓ {title}\nСледующий срок: {result.get('due_at') or '—'}"
        toast = "Готово, перенесено"
    elif result.get("status") == "done":
        note = f"✓ Выполнено: {title}"
        toast = "Выполнено"
    else:
        note = f"✓ {title}"
        toast = "Готово"

    answer_callback(callback_id, toast)
    if msg.get("message_id") is not None and chat_id is not None:
        edit_message_text(chat_id, int(msg["message_id"]), note)


async def handle_incoming_message(update: dict[str, Any]) -> None:
    """Any text message from the owner chat becomes a NoteTask item."""
    msg = update.get("message") or {}
    text = str(msg.get("text") or "").strip()
    if not text:
        return
    from_user = msg.get("from") or {}
    chat = msg.get("chat") or {}
    if str(chat.get("id")) != str(TELEGRAM_CHAT_ID) and str(from_user.get("id")) != str(TELEGRAM_CHAT_ID):
        return
    if text.startswith("/"):
        # Bot commands: keep it minimal for now.
        if text.split(maxsplit=1)[0] in ("/start", "/help"):
            send_telegram(
                "Пришлите любую фразу — станет задачей. "
                "Если не разберу — сохраню как заметку в Inbox."
            )
        return

    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        result = await create_item_from_text(db, text, source="telegram")
    finally:
        await db.close()

    if result.get("type") == "task":
        reply = f"✅ Задача #{result.get('id')}: {result.get('title')}"
    elif result.get("type") == "note":
        reply = f"📝 Заметка в Inbox: {result.get('title')}"
    else:
        reply = result.get("reply") or "Не удалось сохранить"
    send_telegram(reply)


def poll_telegram_updates(offset: int | None) -> tuple[list[dict[str, Any]], int | None]:
    payload: dict[str, Any] = {"timeout": 20, "allowed_updates": ["callback_query", "message"]}
    if offset is not None:
        payload["offset"] = offset
    result = tg_api("getUpdates", payload, timeout=25)
    if not result or not result.get("ok"):
        return [], offset
    updates = result.get("result") or []
    next_offset = offset
    for upd in updates:
        uid = upd.get("update_id")
        if isinstance(uid, int):
            next_offset = uid + 1
    return updates, next_offset


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
                if hourly_ready(now, task.get("remind_at")) and in_hour_fire_window(now):
                    key = hourly_dedupe_key(task["id"], now)
                    title = "Напоминание · каждые 3 часа"
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
    tg_offset: int | None = None
    while not stop.is_set():
        try:
            await tick_once()
        except Exception:
            log.exception("Notify tick failed")

        # Poll TG callbacks between ticks (long-poll up to ~20s).
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                updates, tg_offset = await asyncio.to_thread(poll_telegram_updates, tg_offset)
                for upd in updates:
                    try:
                        if upd.get("callback_query"):
                            await handle_callback_query(upd)
                        elif upd.get("message"):
                            await handle_incoming_message(upd)
                    except Exception:
                        log.exception("Telegram update failed")
            except Exception:
                log.exception("Telegram poll failed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
        else:
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
