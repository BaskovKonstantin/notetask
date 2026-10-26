"""Turn a free Russian phrase into a NoteTask draft. No I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Moscow")

REPEAT_RULES = frozenset(
    {"daily", "every_2_days", "every_3_days", "weekly", "weekdays", "monthly"}
)

REPEAT_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("every_2_days", ("через день", "каждые 2 дня", "каждые два дня")),
    ("every_3_days", ("каждые 3 дня", "каждые три дня")),
    ("weekdays", ("по будням", "по будним", "каждый будний день", "каждый будний")),
    ("daily", ("каждый день", "ежедневно")),
    ("weekly", ("каждую неделю", "еженедельно", "раз в неделю")),
    ("monthly", ("каждый месяц", "ежемесячно", "раз в месяц")),
)

REPEAT_SPEAK = {
    "daily": "каждый день",
    "every_2_days": "через день",
    "every_3_days": "каждые три дня",
    "weekly": "каждую неделю",
    "weekdays": "по будням",
    "monthly": "каждый месяц",
}

WEEKDAYS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("понедельник", "понедельника"), 0),
    (("вторник", "вторника"), 1),
    (("среду", "среда", "среды"), 2),
    (("четверг", "четверга"), 3),
    (("пятницу", "пятница", "пятницы"), 4),
    (("субботу", "суббота", "субботы"), 5),
    (("воскресенье", "воскресенья"), 6),
)

MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

HOURS = {
    "час": 1,
    "один": 1,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
}

PREFIXES = (
    "алиса ",
    "пожалуйста ",
    "добавь задачу ",
    "создай задачу ",
    "поставь задачу ",
    "поставь в задачи ",
    "запиши задачу ",
    "новая задача ",
    "добавь ",
    "создай ",
    "запиши ",
    "поставь ",
    "напомни мне ",
    "напомнить ",
    "напомни ",
    "напоминание ",
)


@dataclass(frozen=True)
class AliceDraft:
    ok: bool
    title: str
    due_at: str | None
    remind_at: str | None
    remind_rule: str | None
    repeat_rule: str | None
    reply: str


def parse_alice(text: str, now: datetime | None = None) -> AliceDraft:
    moment = _as_local(now)
    raw = _norm(text)
    if not raw or raw in {"помощь", "что ты умеешь", "что умеешь", "помоги"}:
        return _fail(_help())

    remind = bool(re.search(r"\bнапомн", raw))
    hourly = bool(
        re.search(r"кажд(?:ый час|ые\s*3\s*час|ые\s*три\s*час)|ежечасно", raw)
    )
    work = raw
    repeat: str | None = None
    weekday: int | None = None
    every_weekday = False

    for rule, phrases in REPEAT_PHRASES:
        for phrase in phrases:
            if phrase in work:
                repeat = rule
                work = work.replace(phrase, " ", 1)
                break
        if repeat:
            break

    every_day_match = re.search(
        r"\bкажд(?:ый|ую|ое)\s+(" + _weekday_pattern() + r")\b",
        work,
    )
    if every_day_match:
        every_weekday = True
        weekday = _weekday_index(every_day_match.group(1))
        repeat = repeat or "weekly"
        work = work.replace(every_day_match.group(0), " ", 1)

    day_match = re.search(
        r"\b(?:до|к|ко|на|во|в)\s+(" + _weekday_pattern() + r")\b",
        work,
    )
    if day_match and weekday is None:
        weekday = _weekday_index(day_match.group(1))
        work = work.replace(day_match.group(0), " ", 1)

    named_day: str | None = None
    for word, key in (
        ("послезавтра", "after"),
        ("завтра", "tomorrow"),
        ("сегодня", "today"),
    ):
        if re.search(rf"\b{word}\b", work):
            named_day = key
            work = re.sub(rf"\b{word}\b", " ", work, count=1)
            break

    month_day = re.search(
        r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?\b",
        work,
    )
    numeric_day = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", work)
    clock = re.search(
        r"\bв\s+(?:(\d{1,2})(?::(\d{2}))?|(" + "|".join(HOURS) + r"))\b",
        work,
    )
    hour: int | None = None
    minute = 0
    if clock:
        if clock.group(3):
            hour = HOURS[clock.group(3)]
        else:
            hour = int(clock.group(1))
            minute = int(clock.group(2) or 0)
        tail = work[clock.end() : clock.end() + 12]
        if re.match(r"\s+вечера\b", tail) and hour < 12:
            hour += 12
        if re.match(r"\s+утра\b", tail) and hour == 12:
            hour = 0
        work = work[: clock.start()] + " " + work[clock.end() :]
        work = re.sub(r"\b(вечера|вечером|утра|утром)\b", " ", work, count=1)

    if month_day:
        work = work.replace(month_day.group(0), " ", 1)
    if numeric_day:
        work = work.replace(numeric_day.group(0), " ", 1)
    if hourly:
        work = re.sub(
            r"кажд(?:ый час|ые\s*3\s*час(?:а|ов)?|ые\s*три\s*час(?:а|ов)?)|ежечасно",
            " ",
            work,
        )

    for prefix in PREFIXES:
        while work.startswith(prefix):
            work = work[len(prefix) :]
    work = re.sub(r"\b(мне|задачу|задача|это)\b", " ", work)
    title = re.sub(r"\s+", " ", work).strip(" -")

    if hour is not None and not 0 <= hour <= 23:
        return _fail("Не разобрала время. Скажи, например, в 9 или в 18:30.")
    if minute > 59:
        return _fail("Не разобрала минуты.")

    day = _resolve_day(
        moment,
        named_day=named_day,
        weekday=weekday,
        month_day=month_day,
        numeric_day=numeric_day,
        hour=hour,
        minute=minute,
        every_weekday=every_weekday,
    )
    if day is False:
        return _fail("Такой даты нет.")

    due_at: str | None = None
    remind_at: str | None = None
    remind_rule: str | None = "hourly" if hourly else None
    if isinstance(day, datetime) or day is not None:
        if hour is None:
            due_at = day.isoformat() if isinstance(day, type(moment.date())) else day.date().isoformat()
        else:
            stamp = datetime(
                day.year if not isinstance(day, datetime) else day.year,
                day.month,
                day.day,
                hour,
                minute,
                tzinfo=TZ,
            )
            if remind:
                remind_at = _iso(stamp)
                due_at = stamp.date().isoformat()
            else:
                due_at = _iso(stamp)
    elif hour is not None:
        stamp = moment.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if stamp <= moment:
            stamp = stamp + timedelta(days=1)
        stamp = _onto_weekday(stamp, repeat)
        if remind or hourly:
            remind_at = _iso(stamp)
            due_at = stamp.date().isoformat()
        else:
            due_at = _iso(stamp)
    elif repeat == "weekdays":
        due_at = _onto_weekday(moment + timedelta(days=1), repeat).date().isoformat()

    if not title:
        return _fail(_help())

    return AliceDraft(
        ok=True,
        title=title,
        due_at=due_at,
        remind_at=remind_at,
        remind_rule=remind_rule,
        repeat_rule=repeat if repeat in REPEAT_RULES else None,
        reply=_speak(title, due_at, remind_at, remind_rule, repeat, moment),
    )


def _resolve_day(
    moment: datetime,
    *,
    named_day: str | None,
    weekday: int | None,
    month_day: re.Match[str] | None,
    numeric_day: re.Match[str] | None,
    hour: int | None,
    minute: int,
    every_weekday: bool,
):
    today = moment.date()
    if named_day == "today":
        return today
    if named_day == "tomorrow":
        return today + timedelta(days=1)
    if named_day == "after":
        return today + timedelta(days=2)
    if weekday is not None:
        return _next_weekday(today, weekday, moment, hour, minute, allow_today=not every_weekday)
    if month_day:
        year = int(month_day.group(3) or today.year)
        try:
            found = datetime(year, MONTHS[month_day.group(2)], int(month_day.group(1))).date()
        except ValueError:
            return False
        if found < today and month_day.group(3) is None:
            try:
                found = found.replace(year=year + 1)
            except ValueError:
                return False
        return found
    if numeric_day:
        year_raw = numeric_day.group(3)
        year = int(year_raw) if year_raw else today.year
        if year < 100:
            year += 2000
        try:
            found = datetime(year, int(numeric_day.group(2)), int(numeric_day.group(1))).date()
        except ValueError:
            return False
        if found < today and year_raw is None:
            try:
                found = found.replace(year=year + 1)
            except ValueError:
                return False
        return found
    return None


def _onto_weekday(stamp: datetime, repeat: str | None) -> datetime:
    if repeat != "weekdays":
        return stamp
    while stamp.weekday() >= 5:
        stamp += timedelta(days=1)
    return stamp


def _next_weekday(today, weekday: int, moment: datetime, hour: int | None, minute: int, allow_today: bool):
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and allow_today:
        if hour is None:
            return today
        stamp = moment.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if stamp > moment:
            return today
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _speak(
    title: str,
    due_at: str | None,
    remind_at: str | None,
    remind_rule: str | None,
    repeat: str | None,
    moment: datetime,
) -> str:
    parts = [f"Записала: {title}."]
    if remind_rule == "hourly":
        parts.append("Напоминание каждые 3 часа, пока не закроешь.")
    elif remind_at:
        parts.append("Напомню " + _human(remind_at, moment) + ".")
    if due_at and due_at != (remind_at or "")[:10]:
        parts.append("Срок " + _human(due_at, moment) + ".")
    if repeat:
        parts.append("Повтор: " + REPEAT_SPEAK.get(repeat, repeat) + ".")
    return " ".join(parts)


def _human(raw: str, moment: datetime) -> str:
    if "T" not in raw:
        day = datetime.fromisoformat(raw).date()
        return _day_name(day, moment.date())
    stamp = datetime.fromisoformat(raw)
    clock = f"{stamp.hour}:{stamp.minute:02d}"
    return _day_name(stamp.date(), moment.date()) + " в " + clock


def _day_name(day, today) -> str:
    if day == today:
        return "сегодня"
    if day == today + timedelta(days=1):
        return "завтра"
    if day == today + timedelta(days=2):
        return "послезавтра"
    names = ("понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье")
    if 0 < (day - today).days < 7:
        return "в " + names[day.weekday()]
    months = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    return f"{day.day} {months[day.month - 1]}"


def _help() -> str:
    return (
        "Скажи задачу своими словами. "
        "Например: напомни завтра в 9 позвонить стоматологу. "
        "Или: каждый понедельник в 8 зарядка. "
        "Или: до пятницы сдать отчёт."
    )


def _fail(reply: str) -> AliceDraft:
    return AliceDraft(False, "", None, None, None, None, reply)


def _as_local(now: datetime | None) -> datetime:
    moment = now or datetime.now(TZ)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=TZ)
    return moment.astimezone(TZ)


def _iso(stamp: datetime) -> str:
    return stamp.replace(microsecond=0).isoformat()


def _norm(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"(\d)\.(\d{2})\b", r"\1:\2", text)
    text = re.sub(r"[!?,;]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _weekday_pattern() -> str:
    names = [name for group, _ in WEEKDAYS for name in group]
    return "|".join(names)


def _weekday_index(name: str) -> int:
    for group, index in WEEKDAYS:
        if name in group:
            return index
    raise ValueError(name)
