"""Complete / reschedule a task (shared by API and Telegram callbacks)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

import aiosqlite

from .config import MORNING_DUE_HOUR, NOTIFY_TZ
from .db import bump_completions, log_action, row_to_dict, utcnow
from .due_utils import next_daily_after_complete


TZ = ZoneInfo(NOTIFY_TZ)


def _hourly_resume_at(new_due: str | None) -> str:
    """Next hourly nag: morning of next due day (or tomorrow)."""
    try:
        day = date.fromisoformat((new_due or "")[:10])
    except ValueError:
        day = datetime.now(TZ).date() + timedelta(days=1)
    today = datetime.now(TZ).date()
    if day <= today:
        day = today + timedelta(days=1)
    return datetime(day.year, day.month, day.day, MORNING_DUE_HOUR, 0, 0, tzinfo=TZ).isoformat()


async def fetch_task_row(db: aiosqlite.Connection, task_id: int) -> dict[str, Any] | None:
    cur = await db.execute(
        "SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL",
        (task_id,),
    )
    row = await cur.fetchone()
    return row_to_dict(row) if row else None


async def complete_task_row(
    db: aiosqlite.Connection,
    task_id: int,
    *,
    normalize_repeat_rule: Callable[[str | None], str | None],
    next_due_from_rule: Callable[[str | None, str | None], str | None],
) -> dict[str, Any] | None:
    """Mark done or roll recurring due.

    One-shot complete clears remind. Recurring + hourly keeps hourly but
    pauses until morning of the next due day (no more nags the same day).
    """
    old = await fetch_task_row(db, task_id)
    if not old:
        return None
    if old["status"] == "done":
        return old
    now = utcnow()
    rule = normalize_repeat_rule(old.get("repeat_rule"))
    was_hourly = (old.get("remind_rule") or "").strip().lower() == "hourly"
    if rule:
        today = date.today()
        if rule == "daily":
            new_due = next_daily_after_complete(old.get("due_at"), today)
        else:
            new_due = next_due_from_rule(old.get("due_at"), rule)
            for _ in range(400):
                d = new_due[:10] if new_due else ""
                if not d or d > today.isoformat():
                    break
                new_due = next_due_from_rule(new_due, rule)
        if was_hourly:
            remind_rule = "hourly"
            remind_at = _hourly_resume_at(new_due)
        else:
            remind_rule = None
            remind_at = None
        await db.execute(
            """
            UPDATE tasks SET due_at=?, due_start=NULL, remind_at=?, remind_rule=?,
              status='open', completed_at=NULL, updated_at=?
            WHERE id=?
            """,
            (new_due, remind_at, remind_rule, now, task_id),
        )
        await bump_completions(db)
        await log_action(
            db,
            "completed",
            "task",
            task_id,
            {
                "title": old["title"],
                "recurring": True,
                "repeat_rule": rule,
                "next_due": new_due,
                "remind_rule": remind_rule,
                "remind_at": remind_at,
            },
        )
        await db.commit()
        task = await fetch_task_row(db, task_id)
        if task is not None:
            task["rescheduled"] = True
        return task
    await db.execute(
        """
        UPDATE tasks SET status='done', completed_at=?, updated_at=?,
          remind_at=NULL, remind_rule=NULL
        WHERE id=?
        """,
        (now, now, task_id),
    )
    await bump_completions(db)
    await log_action(db, "completed", "task", task_id, {"title": old["title"], "cleared_remind": True})
    await db.commit()
    return await fetch_task_row(db, task_id)
