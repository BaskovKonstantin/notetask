"""Complete / reschedule a task (shared by API and Telegram callbacks)."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

import aiosqlite

from .db import bump_completions, log_action, row_to_dict, utcnow
from .due_utils import next_daily_after_complete


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
    """Mark done or roll recurring due. Clears remind so hourly nag stops."""
    old = await fetch_task_row(db, task_id)
    if not old:
        return None
    if old["status"] == "done":
        return old
    now = utcnow()
    rule = normalize_repeat_rule(old.get("repeat_rule"))
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
        await db.execute(
            """
            UPDATE tasks SET due_at=?, due_start=NULL, remind_at=NULL, remind_rule=NULL,
              status='open', completed_at=NULL, updated_at=?
            WHERE id=?
            """,
            (new_due, now, task_id),
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
                "cleared_remind": True,
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
