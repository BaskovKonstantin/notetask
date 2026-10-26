"""Shared inbox logic: turn free text into a NoteTask item.

One entry point for every external source (Alice, Telegram, HTTP inbox):
parse the phrase; on success create a task, otherwise fall back to a note
in the Inbox project so nothing is lost.
"""

from __future__ import annotations

from typing import Any

import aiosqlite

from .alice_parse import parse_alice
from .db import log_action, utcnow
from .remind_utils import next_hour_boundary_iso, normalize_remind_rule


async def _inbox_project_id(db: aiosqlite.Connection) -> int | None:
    cur = await db.execute(
        "SELECT id FROM projects WHERE name='Inbox' AND deleted_at IS NULL LIMIT 1"
    )
    row = await cur.fetchone()
    return int(row["id"]) if row else None


async def create_task_from_draft(
    db: aiosqlite.Connection,
    draft,
    *,
    source: str,
) -> dict[str, Any]:
    """Create a task from a parsed AliceDraft (shared by Alice and the inbox)."""
    remind_at = draft.remind_at
    remind_rule = None
    if draft.remind_rule:
        remind_rule = normalize_remind_rule(draft.remind_rule)
        if remind_rule == "hourly":
            remind_at = next_hour_boundary_iso()

    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO tasks(
          project_id, title, notes, kind, priority, due_at, due_start, remind_at, remind_rule,
          status, created_at, updated_at, location, cost, cost_type, finance_category_id,
          work_project_id, repeat_rule
        )
        VALUES(NULL, ?, '', 'task', 4, ?, NULL, ?, ?, 'open', ?, ?, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (
            draft.title,
            draft.due_at,
            remind_at,
            remind_rule,
            now,
            now,
            draft.repeat_rule,
        ),
    )
    task_id = cur.lastrowid
    await log_action(
        db,
        "created",
        "task",
        task_id,
        {"title": draft.title, "source": source, "due_at": draft.due_at},
    )
    await db.commit()
    return {"type": "task", "id": task_id, "title": draft.title, "reply": draft.reply}


async def create_note_from_text(
    db: aiosqlite.Connection,
    text: str,
    *,
    source: str,
) -> dict[str, Any]:
    """Save raw text as a note in the Inbox project (fallback capture)."""
    title = text.strip()
    if len(title) > 200:
        title = title[:197].rstrip() + "…"
    now = utcnow()
    project_id = await _inbox_project_id(db)
    cur = await db.execute(
        "INSERT INTO notes(project_id, title, body, created_at, updated_at) VALUES(?,?,?,?,?)",
        (project_id, title, text.strip(), now, now),
    )
    note_id = cur.lastrowid
    await log_action(
        db,
        "created",
        "note",
        note_id,
        {"title": title, "source": source},
    )
    await db.commit()
    return {"type": "note", "id": note_id, "title": title}


async def create_item_from_text(
    db: aiosqlite.Connection,
    text: str,
    *,
    source: str,
    note_on_parse_fail: bool = True,
) -> dict[str, Any]:
    """Parse free text and create a task; fall back to an Inbox note.

    Returns {"type": "task"|"note"|"error", ...}.
    """
    raw = (text or "").strip()
    if not raw:
        return {"type": "error", "reply": "Пустой текст"}
    draft = parse_alice(raw)
    if draft.ok:
        return await create_task_from_draft(db, draft, source=source)
    if not note_on_parse_fail:
        return {"type": "error", "reply": draft.reply}
    note = await create_note_from_text(db, raw, source=source)
    note["reply"] = f"Сохранил заметку: {note['title']}"
    return note
