"""Universal inbox API: one token-authenticated endpoint for every external tool.

Anything that can make an HTTP POST (n8n, cron, Kimi automations, shortcuts,
scripts) can drop a task or note into NoteTask:

    curl -X POST "https://baski.pro/todo/api/inbox" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"text": "оплатить интернет завтра в 10", "source": "n8n"}'
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_auth
from .config import (
    ALICE_WEBHOOK_TOKEN,
    INBOX_API_TOKEN,
    PUBLIC_BASE_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from .deps import get_db
from .inbox_core import create_item_from_text

router = APIRouter()


def _inbox_token_ok(given: str) -> bool:
    expected = INBOX_API_TOKEN
    if not expected or not given:
        return False
    return secrets.compare_digest(given, expected)


def _extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-inbox-token", "") or request.query_params.get("token", "")


@router.post("/api/inbox")
async def inbox_ingest(request: Request, db=Depends(get_db)):
    if not _inbox_token_ok(_extract_token(request)):
        raise HTTPException(401, "Invalid token")
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, "Bad request") from exc
    text = str((body or {}).get("text") or "").strip()
    source = str((body or {}).get("source") or "api").strip()[:40] or "api"
    result = await create_item_from_text(db, text, source=source)
    if result.get("type") == "error":
        raise HTTPException(422, result.get("reply") or "Не удалось разобрать текст")
    return result


@router.get("/api/integrations/status")
async def integrations_status(_: dict = Depends(require_auth)):
    """Which entry points are live — feeds the Integrations panel in the SPA."""
    telegram_on = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    return {
        "public_url": PUBLIC_BASE_URL,
        "inbox": {
            "configured": bool(INBOX_API_TOKEN),
            "url": f"{PUBLIC_BASE_URL}/api/inbox",
        },
        "alice": {
            "configured": bool(ALICE_WEBHOOK_TOKEN),
            "url": f"{PUBLIC_BASE_URL}/api/alice",
        },
        "telegram": {
            "configured": telegram_on,
            "inbound": telegram_on,
            "outbound": telegram_on,
        },
        "capture_url": f"{PUBLIC_BASE_URL}/capture",
        "widget_url": f"{PUBLIC_BASE_URL}/widget",
    }
