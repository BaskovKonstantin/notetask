"""Yandex Dialogs webhook: one spoken phrase becomes a NoteTask."""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from .alice_parse import parse_alice
from .db import log_action, utcnow
from .deps import get_db
from .remind_utils import next_hour_boundary_iso, normalize_remind_rule

router = APIRouter()


def _token_ok(given: str) -> bool:
    expected = os.environ.get("ALICE_WEBHOOK_TOKEN", "").strip()
    if not expected or not given:
        return False
    return secrets.compare_digest(given, expected)


def _alice(text: str, end: bool = True) -> dict:
    return {
        "version": "1.0",
        "response": {"text": text, "tts": text, "end_session": end},
    }


@router.post("/api/alice")
async def alice_webhook(request: Request, db=Depends(get_db)):
    token = request.query_params.get("token", "") or request.headers.get("x-alice-token", "")
    if not _token_ok(token):
        raise HTTPException(404, "Not found")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, "Bad request") from exc

    command = str((body.get("request") or {}).get("command") or "").strip()
    draft = parse_alice(command)
    if not draft.ok:
        fresh = bool((body.get("session") or {}).get("new"))
        return _alice(draft.reply, end=not fresh)

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
        {"title": draft.title, "source": "alice", "due_at": draft.due_at},
    )
    await db.commit()
    return _alice(draft.reply, end=True)
