"""Recurring nag reminders (every 3 hours) until task is done / remind cleared."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import NOTIFY_TZ

TZ = ZoneInfo(NOTIFY_TZ)
REMIND_RULES = frozenset({"hourly"})
NAG_INTERVAL_HOURS = 3


def normalize_remind_rule(rule: str | None) -> str | None:
    if rule is None or rule == "" or rule == "none":
        return None
    value = str(rule).strip().lower()
    if value not in REMIND_RULES:
        raise ValueError(f"Invalid remind_rule: {rule}")
    return value


def next_hour_boundary(now: datetime | None = None) -> datetime:
    """Next local 3-hour slot (:00 of 0, 3, 6, 9, 12, 15, 18, 21)."""
    current = now.astimezone(TZ) if now and now.tzinfo else (now or datetime.now(TZ))
    if current.tzinfo is None:
        current = current.replace(tzinfo=TZ)
    floored = current.replace(minute=0, second=0, microsecond=0)
    remainder = floored.hour % NAG_INTERVAL_HOURS
    if remainder == 0 and current <= floored:
        return floored
    add = NAG_INTERVAL_HOURS - remainder if remainder else NAG_INTERVAL_HOURS
    return floored + timedelta(hours=add)


def next_hour_boundary_iso(now: datetime | None = None) -> str:
    return next_hour_boundary(now).replace(microsecond=0).isoformat()


def hourly_dedupe_key(task_id: int, when: datetime) -> str:
    local = when.astimezone(TZ) if when.tzinfo else when.replace(tzinfo=TZ)
    return f"remind:{task_id}:{local.strftime('%Y-%m-%dT%H')}"


def in_hour_fire_window(now: datetime, window_minutes: int = 5) -> bool:
    local = now.astimezone(TZ) if now.tzinfo else now.replace(tzinfo=TZ)
    return local.minute < window_minutes and local.hour % NAG_INTERVAL_HOURS == 0


def hourly_ready(now: datetime, resume_at: str | None) -> bool:
    """True when the 3-hour nag may fire (pause until remind_at reached)."""
    if resume_at is None or not str(resume_at).strip():
        return True
    text = str(resume_at).strip()
    try:
        if text.endswith("Z"):
            resume = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            resume = datetime.fromisoformat(text)
    except ValueError:
        return True
    if resume.tzinfo is None:
        resume = resume.replace(tzinfo=TZ)
    local_now = now.astimezone(TZ) if now.tzinfo else now.replace(tzinfo=TZ)
    return resume.astimezone(TZ) <= local_now
