from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import MORNING_DUE_HOUR, NOTIFY_TZ

TZ = ZoneInfo(NOTIFY_TZ)


def due_at_present(raw: str | None) -> bool:
    if raw is None:
        return False
    return bool(str(raw).strip())


def parse_task_dt(raw: str | None) -> datetime | None:
    if not due_at_present(raw):
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            d = datetime.strptime(text[:10], "%Y-%m-%d")
            return d.replace(tzinfo=TZ, hour=MORNING_DUE_HOUR, minute=0, second=0, microsecond=0)
        except ValueError:
            return None
    if "T" not in text and len(text) <= 10:
        return dt.replace(tzinfo=TZ, hour=MORNING_DUE_HOUR, minute=0, second=0, microsecond=0)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def is_task_overdue(due_at: str | None, now: datetime) -> bool:
    if not due_at_present(due_at):
        return False
    due_dt = parse_task_dt(due_at)
    if due_dt is None:
        return False
    return due_dt.date() < now.date()
