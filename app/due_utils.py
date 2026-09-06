from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .config import MORNING_DUE_HOUR, NOTIFY_TZ

TZ = ZoneInfo(NOTIFY_TZ)


def due_at_present(raw: str | None) -> bool:
    if raw is None:
        return False
    return bool(str(raw).strip())


def due_day(raw: str | None) -> date | None:
    if not due_at_present(raw):
        return None
    text = str(raw).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def normalize_due_start(due_start: str | None, due_at: str | None) -> str | None:
    """Keep YYYY-MM-DD start only when end exists; clamp if start > end day."""
    end = due_day(due_at)
    if end is None:
        return None
    start = due_day(due_start)
    if start is None:
        return None
    if start > end:
        return end.isoformat()
    return start.isoformat()


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


def task_window_overdue(task: Mapping[str, Any], today: date) -> bool:
    end = due_day(task.get("due_at"))
    if end is None:
        return False
    return end < today


def task_in_today_view(task: Mapping[str, Any], today: date) -> bool:
    if task.get("kind") != "task":
        return False
    end = due_day(task.get("due_at"))
    if end is None:
        return False
    start = due_day(task.get("due_start"))
    if start is not None:
        return today >= start
    return end <= today


def task_in_upcoming_view(task: Mapping[str, Any], today: date) -> bool:
    if task.get("kind") != "task":
        return False
    end = due_day(task.get("due_at"))
    if end is None:
        return False
    start = due_day(task.get("due_start"))
    if start is not None:
        return today < start
    return end > today
