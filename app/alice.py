"""Yandex Dialogs webhook: one spoken phrase becomes a NoteTask."""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from .alice_parse import parse_alice
from .deps import get_db
from .inbox_core import create_task_from_draft

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

    result = await create_task_from_draft(db, draft, source="alice")
    return _alice(result["reply"], end=True)
