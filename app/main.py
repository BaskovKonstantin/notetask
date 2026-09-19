from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import aiosqlite
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import make_token, require_auth, verify_password
from .config import DATA_DIR, DB_PATH, PORT
from .db import (
    bump_completions,
    bump_workouts,
    connect,
    ensure_defaults,
    log_action,
    row_to_dict,
    utcnow,
)
from .deps import get_db
from .due_utils import (
    catch_up_daily_due_at,
    normalize_due_start,
    task_in_today_view,
    task_in_upcoming_view,
)
from .remind_utils import next_hour_boundary_iso, normalize_remind_rule as _normalize_remind_rule
from .finance_helpers import (
    reassign_work_payment_project,
    sum_work_payment_income,
    work_payment_received_filter,
    work_payments_has_status,
)
from .finance_sheet import ensure_finance_sheet_defaults, register_finance_sheet
from .finance_task_sync import resolve_finance_category_id
from .goals import ensure_goals_tables, mark_goal_nodes_for_task, register_goals
from .notify import configure_complete_helpers, notify_loop, send_telegram
from .task_complete import complete_task_row
from .workouts import GYM_CODES, advance_next_code, router as workout_plan_router, seed_sport_goals

STATIC = Path(__file__).resolve().parents[1] / "static"
DOWNLOADS_DIR = DATA_DIR / "downloads"

DOWNLOAD_CATALOG = (
    {
        "id": "windows",
        "label": "Windows",
        "filename": "NoteTask-Setup.exe",
        "hint": "Портативный .exe (Photino). Ctrl+Space глобально, автозапуск в Startup.",
    },
    {
        "id": "android",
        "label": "Android",
        "filename": "NoteTask.apk",
        "hint": "APK. После установки: виджет «NoteTask · Сегодня» на рабочий стол.",
    },
)


log = logging.getLogger("notetask")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await connect()
    await ensure_defaults(db)
    await ensure_finance_sheet_defaults(db)
    await ensure_goals_tables(db)
    await seed_sport_goals(db)
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=180)).isoformat()
    await db.execute("DELETE FROM action_log WHERE at < ?", (cutoff,))
    await db.commit()
    await db.close()
    configure_complete_helpers(normalize_repeat_rule, next_due_from_rule)
    stop = asyncio.Event()
    task = asyncio.create_task(notify_loop(stop))
    try:
        yield
    finally:
        stop.set()
        await task


app = FastAPI(title="NoteTask", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")
register_finance_sheet(app)
register_goals(app)
app.include_router(workout_plan_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal error"}, status_code=500)


REPEAT_RULES = {
    "daily",
    "every_2_days",
    "every_3_days",
    "weekly",
    "weekdays",
    "monthly",
}


def parse_due_base(due_at: str | None) -> datetime:
    if due_at:
        raw = due_at.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return dt.replace(hour=12, minute=0, second=0, microsecond=0)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            try:
                d = date.fromisoformat(due_at[:10])
                return datetime(d.year, d.month, d.day, 12, 0, 0)
            except ValueError:
                pass
    today = date.today()
    return datetime(today.year, today.month, today.day, 12, 0, 0)


def add_months(dt: datetime, months: int) -> datetime:
    y = dt.year
    m = dt.month + months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    # clamp day
    for day in range(dt.day, 0, -1):
        try:
            return dt.replace(year=y, month=m, day=day)
        except ValueError:
            continue
    return dt.replace(year=y, month=m, day=1)


def next_due_from_rule(due_at: str | None, rule: str | None) -> str | None:
    if not rule or rule not in REPEAT_RULES:
        return due_at
    base = parse_due_base(due_at)
    had_time = bool(due_at and "T" in due_at)
    if rule == "daily":
        nxt = base + timedelta(days=1)
    elif rule == "every_2_days":
        nxt = base + timedelta(days=2)
    elif rule == "every_3_days":
        nxt = base + timedelta(days=3)
    elif rule == "weekly":
        nxt = base + timedelta(days=7)
    elif rule == "weekdays":
        nxt = base + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
    elif rule == "monthly":
        nxt = add_months(base, 1)
    else:
        return due_at
    if had_time:
        return nxt.replace(microsecond=0).isoformat()
    return nxt.date().isoformat()


def normalize_repeat_rule(rule: str | None) -> str | None:
    if rule is None or rule == "" or rule == "none":
        return None
    if rule not in REPEAT_RULES:
        raise HTTPException(400, f"Invalid repeat_rule: {rule}")
    return rule


def normalize_remind_rule(rule: str | None) -> str | None:
    try:
        return _normalize_remind_rule(rule)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def prepare_remind_fields(
    remind_at: str | None,
    remind_rule: str | None,
) -> tuple[str | None, str | None]:
    rule = normalize_remind_rule(remind_rule)
    if rule == "hourly":
        return next_hour_boundary_iso(), rule
    return remind_at, None


# ---------- schemas ----------

class LoginIn(BaseModel):
    password: str


class ProjectIn(BaseModel):
    name: str
    color: str = "#2f6f4e"


class TaskIn(BaseModel):
    title: str
    notes: str = ""
    kind: Literal["task", "idea", "plan"] = "task"
    priority: int = Field(default=4, ge=1, le=4)
    due_at: str | None = None
    due_start: str | None = None
    remind_at: str | None = None
    remind_rule: str | None = None
    project_id: int | None = None
    status: Literal["open", "done"] | None = None
    location: str | None = None
    cost: float | None = None
    cost_type: Literal["expense", "income"] | None = None
    finance_category_id: int | None = None
    work_project_id: int | None = None
    repeat_rule: str | None = None


class TaskPatchIn(BaseModel):
    title: str | None = None
    notes: str | None = None
    kind: Literal["task", "idea", "plan"] | None = None
    priority: int | None = Field(default=None, ge=1, le=4)
    due_at: str | None = None
    due_start: str | None = None
    remind_at: str | None = None
    remind_rule: str | None = None
    project_id: int | None = None
    status: Literal["open", "done"] | None = None
    location: str | None = None
    cost: float | None = None
    cost_type: Literal["expense", "income"] | None = None
    finance_category_id: int | None = None
    work_project_id: int | None = None
    repeat_rule: str | None = None


class NoteIn(BaseModel):
    title: str
    body: str = ""
    project_id: int | None = None


class WorkoutSetIn(BaseModel):
    exercise: str
    weight: float | None = None
    reps: int | None = None
    set_index: int = 1
    notes: str = ""
    exercise_id: int | None = None


class WorkoutIn(BaseModel):
    title: str = "Тренировка"
    notes: str = ""
    started_at: str | None = None
    sets: list[WorkoutSetIn] = Field(default_factory=list)
    day_code: str | None = None


class EventIn(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    entity_type: str = Field(default="ui", min_length=1, max_length=32)
    entity_id: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class FinanceMonthIn(BaseModel):
    income: float = 0
    expense: float = 0
    notes: str = ""


class WorkProjectIn(BaseModel):
    title: str
    status: Literal["active", "paused", "done"] = "active"
    client: str = ""
    budget: float | None = None
    notes: str = ""


WORK_PAYMENT_STATUSES = ("received", "planned")


class WorkPaymentIn(BaseModel):
    amount: float = Field(gt=0)
    paid_at: str | None = None
    note: str = ""
    status: Literal["received", "planned"] = "received"


class WorkPaymentPatch(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    paid_at: str | None = None
    note: str | None = None
    status: Literal["received", "planned"] | None = None
    work_project_id: int | None = None


class HealthProfileIn(BaseModel):
    metrics: dict[str, str] = Field(default_factory=dict)
    body: dict[str, dict[str, str]] = Field(default_factory=dict)


class HealthNoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


HEALTH_STATUSES = ("ok", "warn", "bad", "unknown")


def normalize_health_status(raw: str | None) -> str:
    value = str(raw or "ok").strip().lower()
    if value in HEALTH_STATUSES:
        return value
    return "ok"


# Legacy coarse zones + detailed map. Old rows keep working.
HEALTH_REGION_IDS = (
    "head",
    "hair",
    "eyes",
    "nose",
    "ears",
    "jaw",
    "teeth",
    "neck",
    "shoulders",
    "chest",
    "back",
    "stomach",
    "arms",
    "elbows",
    "wrists",
    "hands",
    "hips",
    "legs",
    "thighs",
    "knees",
    "calves",
    "feet",
)


class WorkoutGoalIn(BaseModel):
    title: str
    target: float = 0
    unit: str = ""
    current: float = 0
    period: Literal["week", "month", "year"] = "month"


# ---------- helpers ----------

def diff_fields(old: dict[str, Any], new: dict[str, Any], fields: list[str]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for field in fields:
        old_val = old.get(field)
        new_val = new.get(field)
        if old_val != new_val:
            changes[field] = {"from": old_val, "to": new_val}
    return changes

async def fetch_task(db: aiosqlite.Connection, task_id: int) -> dict[str, Any]:
    cur = await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    row = row_to_dict(await cur.fetchone())
    if not row or row["deleted_at"]:
        raise HTTPException(404, "Task not found")
    return row


async def fetch_note(db: aiosqlite.Connection, note_id: int) -> dict[str, Any]:
    cur = await db.execute("SELECT * FROM notes WHERE id=?", (note_id,))
    row = row_to_dict(await cur.fetchone())
    if not row or row["deleted_at"]:
        raise HTTPException(404, "Note not found")
    return row


async def fetch_workout(db: aiosqlite.Connection, session_id: int) -> dict[str, Any]:
    cur = await db.execute("SELECT * FROM workout_sessions WHERE id=?", (session_id,))
    row = row_to_dict(await cur.fetchone())
    if not row or row["deleted_at"]:
        raise HTTPException(404, "Workout not found")
    cur = await db.execute(
        "SELECT * FROM workout_sets WHERE session_id=? ORDER BY exercise, set_index, id",
        (session_id,),
    )
    row["sets"] = [row_to_dict(r) for r in await cur.fetchall()]
    return row


# ---------- auth / health ----------

@app.get("/api/health")
async def health():
    return {"ok": True, "service": "notetask"}


@app.get("/api/notifications")
async def list_notifications(
    unread: int = 0,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    if unread:
        cur = await db.execute(
            """
            SELECT * FROM app_notifications
            WHERE read_at IS NULL
            ORDER BY id DESC
            LIMIT 50
            """
        )
    else:
        cur = await db.execute(
            "SELECT * FROM app_notifications ORDER BY id DESC LIMIT 50"
        )
    return [row_to_dict(r) for r in await cur.fetchall()]


@app.post("/api/notifications/{item_id}/read")
async def mark_notification_read(
    item_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await db.execute(
        "UPDATE app_notifications SET read_at=? WHERE id=? AND read_at IS NULL",
        (utcnow(), item_id),
    )
    await db.commit()
    return {"ok": True}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await db.execute(
        "UPDATE app_notifications SET read_at=? WHERE read_at IS NULL",
        (utcnow(),),
    )
    await db.commit()
    return {"ok": True}


@app.post("/api/notifications/test")
async def test_notification(_: dict = Depends(require_auth)):
    ok = await asyncio.to_thread(
        send_telegram,
        "NoteTask: тестовое уведомление. Канал Telegram работает.",
    )
    if not ok:
        raise HTTPException(502, "Telegram send failed")
    return {"ok": True}


@app.post("/api/login")
async def login(body: LoginIn, db: aiosqlite.Connection = Depends(get_db)):
    if not verify_password(body.password):
        raise HTTPException(401, "Wrong password")
    await log_action(db, "login", "session", None, {})
    await db.commit()
    return {"token": make_token()}



async def normalize_work_project_id(
    db: aiosqlite.Connection,
    project_id: int | None,
    work_project_id: int | None,
) -> int | None:
    if work_project_id is None:
        return None
    if project_id is not None:
        cur = await db.execute(
            "SELECT name FROM projects WHERE id=? AND deleted_at IS NULL",
            (project_id,),
        )
        row = await cur.fetchone()
        if not row or row["name"] != "Работа":
            return None
    cur = await db.execute(
        "SELECT id FROM work_projects WHERE id=? AND deleted_at IS NULL",
        (work_project_id,),
    )
    if not await cur.fetchone():
        return None
    return work_project_id


# ---------- projects ----------

@app.get("/api/projects")
async def list_projects(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY sort, id"
    )
    projects = [row_to_dict(r) for r in await cur.fetchall()]
    cur = await db.execute(
        """
        SELECT project_id, COUNT(*) AS c FROM tasks
        WHERE deleted_at IS NULL AND status='open'
        GROUP BY project_id
        """
    )
    counts: dict[Any, int] = {}
    for r in await cur.fetchall():
        d = row_to_dict(r)
        counts[d["project_id"]] = int(d["c"] or 0)
    null_open = counts.get(None, 0)
    for p in projects:
        own = counts.get(p["id"], 0)
        if p["name"] == "Inbox":
            p["open_count"] = own + null_open
        else:
            p["open_count"] = own
    return projects


@app.post("/api/projects")
async def create_project(
    body: ProjectIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        "INSERT INTO projects(name, color, sort, created_at, updated_at) VALUES(?,?,?,?,?)",
        (body.name.strip(), body.color, 99, now, now),
    )
    await log_action(db, "created", "project", cur.lastrowid, {"name": body.name})
    await db.commit()
    cur = await db.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,))
    return row_to_dict(await cur.fetchone())


# ---------- tasks ----------

async def catch_up_open_daily_tasks(
    db: aiosqlite.Connection,
    rows: list[dict],
    today: date,
) -> list[dict]:
    """Persist daily open tasks: overdue due_at → today (keep time)."""
    changed = False
    now = utcnow()
    for t in rows:
        if t.get("status") != "open" or t.get("kind") != "task":
            continue
        if (t.get("repeat_rule") or "") != "daily":
            continue
        new_due = catch_up_daily_due_at(t.get("due_at"), today)
        if new_due == t.get("due_at"):
            continue
        await db.execute(
            "UPDATE tasks SET due_at=?, updated_at=? WHERE id=?",
            (new_due, now, t["id"]),
        )
        t["due_at"] = new_due
        changed = True
    if changed:
        await db.commit()
    return rows


@app.get("/api/tasks")
async def list_tasks(
    view: str = "all",
    project_id: int | None = None,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        "SELECT * FROM tasks WHERE deleted_at IS NULL ORDER BY "
        "CASE status WHEN 'open' THEN 0 ELSE 1 END, "
        "CASE WHEN status='done' THEN completed_at END DESC, "
        "CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at, priority, id DESC"
    )
    rows = [row_to_dict(r) for r in await cur.fetchall()]
    if project_id is not None:
        cur = await db.execute(
            "SELECT id FROM projects WHERE id=? AND deleted_at IS NULL AND name='Inbox'",
            (project_id,),
        )
        inbox = await cur.fetchone()
        if inbox:
            rows = [t for t in rows if t["project_id"] == project_id or t["project_id"] is None]
        else:
            rows = [t for t in rows if t["project_id"] == project_id]
    today = date.today()
    rows = await catch_up_open_daily_tasks(db, rows, today)
    if view == "today":
        return [t for t in rows if task_in_today_view(t, today)]
    if view == "upcoming":
        return [t for t in rows if task_in_upcoming_view(t, today)]
    if view == "inbox":
        return [t for t in rows if t["kind"] == "task" and not t["due_at"]]
    if view == "someday":
        return [t for t in rows if t["kind"] in ("idea", "plan")]
    if view == "open":
        return [t for t in rows if t["status"] == "open"]
    return rows


@app.post("/api/tasks")
async def create_task(
    body: TaskIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    work_project_id = await normalize_work_project_id(db, body.project_id, body.work_project_id)
    due_start = normalize_due_start(body.due_start, body.due_at)
    remind_at, remind_rule = prepare_remind_fields(body.remind_at, body.remind_rule)
    finance_category_id = await resolve_finance_category_id(
        db,
        project_id=body.project_id,
        cost_type=body.cost_type,
        finance_category_id=body.finance_category_id,
        has_cost=body.cost is not None and float(body.cost) != 0,
    )
    cur = await db.execute(
        """
        INSERT INTO tasks(
          project_id, title, notes, kind, priority, due_at, due_start, remind_at, remind_rule,
          status, created_at, updated_at, location, cost, cost_type, finance_category_id,
          work_project_id, repeat_rule
        )
        VALUES(?,?,?,?,?,?,?,?,?,'open',?,?,?,?,?,?,?,?)
        """,
        (
            body.project_id,
            body.title.strip(),
            body.notes,
            body.kind,
            body.priority,
            body.due_at,
            due_start,
            remind_at,
            remind_rule,
            now,
            now,
            body.location,
            body.cost,
            body.cost_type,
            finance_category_id,
            work_project_id,
            normalize_repeat_rule(body.repeat_rule),
        ),
    )
    tid = cur.lastrowid
    await log_action(
        db,
        "created",
        "task",
        tid,
        {"title": body.title, "kind": body.kind, "due_at": body.due_at, "due_start": due_start},
    )
    await db.commit()
    return await fetch_task(db, tid)


@app.patch("/api/tasks/{task_id}")
async def patch_task(
    task_id: int,
    body: TaskPatchIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_task(db, task_id)
    patch = body.model_dump(exclude_unset=True)
    next_values = {**old, **patch}
    if "title" in patch and patch["title"] is not None:
        next_values["title"] = patch["title"].strip()
    status = next_values["status"]
    completed_at = old["completed_at"]
    if status == "done" and old["status"] != "done":
        completed_at = utcnow()
        await bump_completions(db)
        await log_action(
            db,
            "completed",
            "task",
            task_id,
            {"title": next_values["title"], "changes": diff_fields(old, next_values, ["status"])},
        )
    elif status == "open" and old["status"] == "done":
        completed_at = None
        await log_action(
            db,
            "reopened",
            "task",
            task_id,
            {"title": next_values["title"], "changes": diff_fields(old, next_values, ["status"])},
        )
    else:
        changes = diff_fields(old, next_values, list(patch.keys()))
        if changes:
            await log_action(
                db,
                "updated",
                "task",
                task_id,
                {"title": next_values["title"], "changes": changes},
            )

    next_values["work_project_id"] = await normalize_work_project_id(
        db, next_values.get("project_id"), next_values.get("work_project_id")
    )
    next_values["due_start"] = normalize_due_start(
        next_values.get("due_start"), next_values.get("due_at")
    )
    if "remind_at" in patch and "remind_rule" not in patch:
        next_values["remind_rule"] = None
    remind_at, remind_rule = prepare_remind_fields(
        next_values.get("remind_at"), next_values.get("remind_rule")
    )
    next_values["remind_at"] = remind_at
    next_values["remind_rule"] = remind_rule
    has_cost = next_values.get("cost") is not None and float(next_values.get("cost") or 0) != 0
    if "finance_category_id" in patch:
        next_values["finance_category_id"] = await resolve_finance_category_id(
            db,
            project_id=next_values.get("project_id"),
            cost_type=next_values.get("cost_type"),
            finance_category_id=patch.get("finance_category_id"),
            has_cost=has_cost,
        )
    elif has_cost and (
        "project_id" in patch or "cost_type" in patch or "cost" in patch
    ):
        next_values["finance_category_id"] = await resolve_finance_category_id(
            db,
            project_id=next_values.get("project_id"),
            cost_type=next_values.get("cost_type"),
            has_cost=True,
        )

    await db.execute(
        """
        UPDATE tasks SET project_id=?, title=?, notes=?, kind=?, priority=?, due_at=?, due_start=?, remind_at=?,
          remind_rule=?, status=?, completed_at=?, updated_at=?, location=?, cost=?, cost_type=?, work_project_id=?,
          finance_category_id=?, repeat_rule=?
        WHERE id=?
        """,
        (
            next_values["project_id"],
            next_values["title"],
            next_values["notes"],
            next_values["kind"],
            next_values["priority"],
            next_values["due_at"],
            next_values.get("due_start"),
            next_values["remind_at"],
            next_values.get("remind_rule"),
            status,
            completed_at,
            utcnow(),
            next_values.get("location"),
            next_values.get("cost"),
            next_values.get("cost_type"),
            next_values.get("work_project_id"),
            next_values.get("finance_category_id"),
            normalize_repeat_rule(next_values.get("repeat_rule")),
            task_id,
        ),
    )
    await db.commit()
    if status == "done" and old["status"] != "done":
        await mark_goal_nodes_for_task(db, task_id)
    return await fetch_task(db, task_id)


@app.put("/api/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: TaskIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_task(db, task_id)
    status = body.status or old["status"]
    completed_at = old["completed_at"]
    remind_at, remind_rule = prepare_remind_fields(body.remind_at, body.remind_rule)
    next_values = {
        "project_id": body.project_id,
        "title": body.title.strip(),
        "notes": body.notes,
        "kind": body.kind,
        "priority": body.priority,
        "due_at": body.due_at,
        "due_start": normalize_due_start(body.due_start, body.due_at),
        "remind_at": remind_at,
        "remind_rule": remind_rule,
        "status": status,
        "location": body.location,
        "cost": body.cost,
        "cost_type": body.cost_type,
        "finance_category_id": body.finance_category_id,
        "work_project_id": body.work_project_id,
        "repeat_rule": body.repeat_rule,
    }
    next_values["work_project_id"] = await normalize_work_project_id(
        db, next_values.get("project_id"), next_values.get("work_project_id")
    )
    next_values["finance_category_id"] = await resolve_finance_category_id(
        db,
        project_id=next_values.get("project_id"),
        cost_type=next_values.get("cost_type"),
        finance_category_id=body.finance_category_id,
        has_cost=body.cost is not None and float(body.cost) != 0,
    )
    if status == "done" and old["status"] != "done":
        completed_at = utcnow()
        await bump_completions(db)
        await log_action(
            db,
            "completed",
            "task",
            task_id,
            {"title": next_values["title"], "changes": diff_fields(old, next_values, ["status"])},
        )
    elif status == "open" and old["status"] == "done":
        completed_at = None
        await log_action(
            db,
            "reopened",
            "task",
            task_id,
            {"title": next_values["title"], "changes": diff_fields(old, next_values, ["status"])},
        )
    else:
        changes = diff_fields(old, next_values, list(next_values.keys()))
        if changes:
            await log_action(
                db,
                "updated",
                "task",
                task_id,
                {"title": next_values["title"], "changes": changes},
            )

    await db.execute(
        """
        UPDATE tasks SET project_id=?, title=?, notes=?, kind=?, priority=?, due_at=?, due_start=?, remind_at=?,
          remind_rule=?, status=?, completed_at=?, updated_at=?, location=?, cost=?, cost_type=?, work_project_id=?,
          finance_category_id=?, repeat_rule=?
        WHERE id=?
        """,
        (
            next_values["project_id"],
            next_values["title"],
            next_values["notes"],
            next_values["kind"],
            next_values["priority"],
            next_values["due_at"],
            next_values.get("due_start"),
            next_values["remind_at"],
            next_values.get("remind_rule"),
            status,
            completed_at,
            utcnow(),
            next_values["location"],
            next_values["cost"],
            next_values["cost_type"],
            next_values["work_project_id"],
            next_values["finance_category_id"],
            normalize_repeat_rule(next_values.get("repeat_rule")),
            task_id,
        ),
    )
    await db.commit()
    if status == "done" and old["status"] != "done":
        await mark_goal_nodes_for_task(db, task_id)
    return await fetch_task(db, task_id)


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(
    task_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    result = await complete_task_row(
        db,
        task_id,
        normalize_repeat_rule=normalize_repeat_rule,
        next_due_from_rule=next_due_from_rule,
    )
    if result is None:
        raise HTTPException(404, "Not found")
    return result


@app.post("/api/tasks/{task_id}/promote")
async def promote_idea(
    task_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_task(db, task_id)
    today = date.today().isoformat()
    await db.execute(
        "UPDATE tasks SET kind='task', due_at=COALESCE(due_at, ?), updated_at=? WHERE id=?",
        (today, utcnow(), task_id),
    )
    await log_action(db, "promoted", "task", task_id, {"from": old["kind"], "title": old["title"]})
    await db.commit()
    return await fetch_task(db, task_id)


@app.delete("/api/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_task(db, task_id)
    now = utcnow()
    await db.execute("UPDATE tasks SET deleted_at=?, updated_at=? WHERE id=?", (now, now, task_id))
    await log_action(db, "deleted", "task", task_id, {"title": old["title"]})
    await db.commit()
    return {"ok": True}


# ---------- notes ----------

@app.get("/api/notes")
async def list_notes(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM notes WHERE deleted_at IS NULL ORDER BY updated_at DESC"
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


@app.post("/api/notes")
async def create_note(
    body: NoteIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        "INSERT INTO notes(project_id, title, body, created_at, updated_at) VALUES(?,?,?,?,?)",
        (body.project_id, body.title.strip(), body.body, now, now),
    )
    nid = cur.lastrowid
    await log_action(db, "created", "note", nid, {"title": body.title})
    await db.commit()
    return await fetch_note(db, nid)


@app.patch("/api/notes/{note_id}")
async def update_note(
    note_id: int,
    body: NoteIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_note(db, note_id)
    next_values = {
        "project_id": body.project_id,
        "title": body.title.strip(),
        "body": body.body,
    }
    changes = diff_fields(old, next_values, list(next_values.keys()))
    await db.execute(
        "UPDATE notes SET project_id=?, title=?, body=?, updated_at=? WHERE id=?",
        (next_values["project_id"], next_values["title"], next_values["body"], utcnow(), note_id),
    )
    if changes:
        await log_action(db, "updated", "note", note_id, {"title": next_values["title"], "changes": changes})
    await db.commit()
    return await fetch_note(db, note_id)


@app.delete("/api/notes/{note_id}")
async def delete_note(
    note_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_note(db, note_id)
    now = utcnow()
    await db.execute("UPDATE notes SET deleted_at=?, updated_at=? WHERE id=?", (now, now, note_id))
    await log_action(db, "deleted", "note", note_id, {"title": old["title"]})
    await db.commit()
    return {"ok": True}


# ---------- workouts ----------

@app.get("/api/workouts")
async def list_workouts(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM workout_sessions WHERE deleted_at IS NULL ORDER BY started_at DESC, id DESC"
    )
    sessions = [row_to_dict(r) for r in await cur.fetchall()]
    out = []
    for s in sessions:
        cur = await db.execute(
            "SELECT * FROM workout_sets WHERE session_id=? ORDER BY exercise, set_index, id",
            (s["id"],),
        )
        s["sets"] = [row_to_dict(r) for r in await cur.fetchall()]
        out.append(s)
    return out


@app.post("/api/workouts")
async def create_workout(
    body: WorkoutIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    started = body.started_at or now
    cur = await db.execute(
        "SELECT id FROM workout_programs WHERE status='active' ORDER BY id LIMIT 1"
    )
    program_row = await cur.fetchone()
    program_id = program_row[0] if program_row else None
    cur = await db.execute(
        """
        INSERT INTO workout_sessions(
            title, notes, started_at, created_at, updated_at, day_code, program_id
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (body.title.strip() or "Тренировка", body.notes, started, now, now, body.day_code, program_id),
    )
    sid = cur.lastrowid
    for s in body.sets:
        await db.execute(
            """
            INSERT INTO workout_sets(
                session_id, exercise, weight, reps, set_index, notes, exercise_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (sid, s.exercise.strip(), s.weight, s.reps, s.set_index, s.notes, s.exercise_id),
        )
    if body.day_code in GYM_CODES:
        await advance_next_code(db, body.day_code)
    await bump_workouts(db, started[:10])
    await log_action(
        db,
        "workout_logged",
        "workout",
        sid,
        {"title": body.title, "sets": len(body.sets), "started_at": started},
    )
    await db.commit()
    return await fetch_workout(db, sid)


@app.delete("/api/workouts/{session_id}")
async def delete_workout(
    session_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_workout(db, session_id)
    now = utcnow()
    await db.execute(
        "UPDATE workout_sessions SET deleted_at=?, updated_at=? WHERE id=?",
        (now, now, session_id),
    )
    await log_action(db, "deleted", "workout", session_id, {"title": old["title"]})
    await db.commit()
    return {"ok": True}


# ---------- history / stats / backup ----------

@app.post("/api/events")
async def record_event(
    body: EventIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await log_action(db, body.action, body.entity_type, body.entity_id, body.payload)
    await db.commit()
    return {"ok": True}


@app.get("/api/history")
async def history(
    limit: int = 100,
    entity_type: str | None = None,
    action: str | None = None,
    since: str | None = None,
    until: str | None = None,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    clauses: list[str] = []
    params: list[Any] = []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if action:
        clauses.append("action = ?")
        params.append(action)
    if since:
        clauses.append("at >= ?")
        params.append(since)
    if until:
        clauses.append("at <= ?")
        params.append(until)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(min(limit, 500))
    cur = await db.execute(
        f"SELECT * FROM action_log {where} ORDER BY id DESC LIMIT ?",
        params,
    )
    rows = []
    for r in await cur.fetchall():
        d = row_to_dict(r)
        try:
            d["payload"] = json.loads(d.pop("payload_json") or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        rows.append(d)
    return rows


@app.get("/api/stats")
async def stats(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    cur = await db.execute(
        "SELECT day, completions, workouts FROM daily_stats WHERE day >= ?",
        (days[0],),
    )
    by_day = {r["day"]: row_to_dict(r) for r in await cur.fetchall()}
    series = [
        {
            "day": d,
            "completions": (by_day.get(d) or {}).get("completions", 0),
            "workouts": (by_day.get(d) or {}).get("workouts", 0),
        }
        for d in days
    ]
    # streak: consecutive days with completions > 0 ending today or yesterday
    streak = 0
    cursor = today
    while True:
        key = cursor.isoformat()
        c = (by_day.get(key) or {}).get("completions", 0)
        if c > 0:
            streak += 1
            cursor -= timedelta(days=1)
            continue
        if cursor == today:
            cursor -= timedelta(days=1)
            continue
        break
    total_done = sum(x["completions"] for x in series)
    total_workouts = sum(x["workouts"] for x in series)
    cur = await db.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE deleted_at IS NULL AND status='open' AND kind='task'"
    )
    open_tasks = (await cur.fetchone())["c"]
    cur = await db.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE deleted_at IS NULL AND status='open' AND kind IN ('idea','plan')"
    )
    ideas = (await cur.fetchone())["c"]
    finance_day = "COALESCE(SUBSTR(completed_at,1,10), SUBSTR(due_at,1,10), SUBSTR(created_at,1,10))"
    cur = await db.execute(
        f"""
        SELECT cost_type, SUM(cost) AS total
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
          AND {finance_day} >= ?
        GROUP BY cost_type
        """,
        (days[0],),
    )
    finance_totals = {"expense": 0.0, "income": 0.0}
    for row in await cur.fetchall():
        d = row_to_dict(row)
        if d["cost_type"] in finance_totals:
            finance_totals[d["cost_type"]] = float(d["total"] or 0)
    finance_totals["income"] += float(
        await sum_work_payment_income(db, since_day=days[0])
    )
    cur = await db.execute(
        """
        SELECT id, title, cost, cost_type, due_at, completed_at, location, project_id
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
        ORDER BY updated_at DESC
        LIMIT 25
        """
    )
    finance_entries = [row_to_dict(r) for r in await cur.fetchall()]
    return {
        "series": series,
        "streak": streak,
        "completions_30d": total_done,
        "workouts_30d": total_workouts,
        "open_tasks": open_tasks,
        "ideas": ideas,
        "finance": {
            "expense_30d": finance_totals["expense"],
            "income_30d": finance_totals["income"],
            "balance_30d": finance_totals["income"] - finance_totals["expense"],
            "entries": finance_entries,
        },
    }


# ---------- section panels ----------

@app.get("/api/finance/months")
async def list_finance_months(
    months: int = 12,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    today = date.today()
    keys: list[str] = []
    y, m = today.year, today.month
    for _ in range(max(1, min(months, 36))):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    cur = await db.execute(
        f"SELECT * FROM finance_months WHERE year_month IN ({','.join('?' * len(keys))})",
        keys,
    )
    saved = {row_to_dict(r)["year_month"]: row_to_dict(r) for r in await cur.fetchall()}
    day_expr = "COALESCE(SUBSTR(completed_at,1,10), SUBSTR(due_at,1,10), SUBSTR(created_at,1,10))"
    cur = await db.execute(
        f"""
        SELECT SUBSTR({day_expr},1,7) AS ym, cost_type, SUM(cost) AS total
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
          AND SUBSTR({day_expr},1,7) IN ({','.join('?' * len(keys))})
        GROUP BY ym, cost_type
        """,
        keys,
    )
    from_tasks: dict[str, dict[str, float]] = {}
    for row in await cur.fetchall():
        d = row_to_dict(row)
        bucket = from_tasks.setdefault(d["ym"], {"expense": 0.0, "income": 0.0})
        if d["cost_type"] in ("expense", "income"):
            bucket[d["cost_type"]] = float(d["total"] or 0)
    from_work = await sum_work_payment_income(db, year_months=keys)
    out = []
    for ym in keys:
        has_row = ym in saved
        row = saved.get(ym) or {"year_month": ym, "income": 0, "expense": 0, "notes": ""}
        task_totals = from_tasks.get(ym, {"expense": 0.0, "income": 0.0})
        manual_income = float(row.get("income") or 0) if has_row else 0.0
        manual_expense = float(row.get("expense") or 0) if has_row else 0.0
        task_income = float(task_totals["income"])
        task_expense = float(task_totals["expense"])
        work_income = float(from_work.get(ym, 0.0))
        income = manual_income + task_income + work_income
        expense = manual_expense + task_expense
        out.append(
            {
                "year_month": ym,
                "manual_income": manual_income,
                "manual_expense": manual_expense,
                "task_income": task_income,
                "task_expense": task_expense,
                "work_income": work_income,
                "income": income,
                "expense": expense,
                "notes": row.get("notes") or "",
                "balance": income - expense,
                "saved": has_row,
            }
        )
    total_income = sum(x["income"] for x in out)
    total_expense = sum(x["expense"] for x in out)
    return {
        "months": out,
        "totals": {
            "income": total_income,
            "expense": total_expense,
            "balance": total_income - total_expense,
            "task_income": sum(x["task_income"] for x in out),
            "task_expense": sum(x["task_expense"] for x in out),
            "work_income": sum(x["work_income"] for x in out),
            "manual_income": sum(x["manual_income"] for x in out),
            "manual_expense": sum(x["manual_expense"] for x in out),
        },
    }



@app.get("/api/finance/months/{year_month}")
async def get_finance_month(
    year_month: str,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    if not re.fullmatch(r"\d{4}-\d{2}", year_month):
        raise HTTPException(400, "year_month must be YYYY-MM")
    day_expr = "COALESCE(SUBSTR(completed_at,1,10), SUBSTR(due_at,1,10), SUBSTR(created_at,1,10))"
    cur = await db.execute(
        f"""
        SELECT cost_type, SUM(cost) AS total
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
          AND SUBSTR({day_expr},1,7) = ?
        GROUP BY cost_type
        """,
        (year_month,),
    )
    task_income = 0.0
    task_expense = 0.0
    for row in await cur.fetchall():
        d = row_to_dict(row)
        if d["cost_type"] == "income":
            task_income = float(d["total"] or 0)
        elif d["cost_type"] == "expense":
            task_expense = float(d["total"] or 0)

    cur = await db.execute(
        "SELECT income, expense, notes FROM finance_months WHERE year_month=?",
        (year_month,),
    )
    saved = await cur.fetchone()
    manual_income = float(saved["income"] or 0) if saved else 0.0
    manual_expense = float(saved["expense"] or 0) if saved else 0.0
    notes = (saved["notes"] if saved else "") or ""

    work_income = float(await sum_work_payment_income(db, year_month=year_month))
    # panel shows task- and work-payment-driven totals (manual kept for API compatibility)
    income = task_income + work_income
    expense = task_expense
    cur = await db.execute(
        f"""
        SELECT id, title, cost, cost_type, due_at, completed_at, created_at, location, project_id, status
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
          AND SUBSTR({day_expr},1,7) = ?
        ORDER BY {day_expr} DESC, id DESC
        LIMIT 100
        """,
        (year_month,),
    )
    entries = []
    for row in await cur.fetchall():
        d = row_to_dict(row)
        day = None
        for key in ("completed_at", "due_at", "created_at"):
            if d.get(key):
                day = str(d[key])[:10]
                break
        d["day"] = day
        d["entry_type"] = "task"
        entries.append(d)

    has_status = await work_payments_has_status(db)
    status_sql = work_payment_received_filter(has_status, alias="p")
    cur = await db.execute(
        f"""
        SELECT p.id, p.amount, p.paid_at, p.note, w.title AS project_title
        FROM work_project_payments p
        JOIN work_projects w ON w.id = p.work_project_id AND w.deleted_at IS NULL
        WHERE p.amount > 0{status_sql}
          AND SUBSTR(p.paid_at, 1, 7) = ?
        ORDER BY p.paid_at DESC, p.id DESC
        LIMIT 100
        """,
        (year_month,),
    )
    for row in await cur.fetchall():
        d = row_to_dict(row)
        note = (d.get("note") or "").strip()
        title = f"{d['project_title']}: {note}" if note else str(d["project_title"])
        entries.append(
            {
                "id": d["id"],
                "entry_type": "work_payment",
                "title": title,
                "cost": float(d["amount"] or 0),
                "cost_type": "income",
                "day": str(d["paid_at"])[:10] if d.get("paid_at") else None,
            }
        )
    entries.sort(key=lambda e: (e.get("day") or "", e.get("id") or 0), reverse=True)

    return {
        "year_month": year_month,
        "task_income": task_income,
        "task_expense": task_expense,
        "work_income": work_income,
        "manual_income": manual_income,
        "manual_expense": manual_expense,
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "notes": notes,
        "saved": saved is not None,
        "entries": entries,
    }


@app.put("/api/finance/months/{year_month}")
async def upsert_finance_month(
    year_month: str,
    body: FinanceMonthIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    if not re.fullmatch(r"\d{4}-\d{2}", year_month):
        raise HTTPException(400, "year_month must be YYYY-MM")
    now = utcnow()
    await db.execute(
        """
        INSERT INTO finance_months(year_month, income, expense, notes, updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(year_month) DO UPDATE SET
          income=excluded.income, expense=excluded.expense, notes=excluded.notes, updated_at=excluded.updated_at
        """,
        (year_month, body.income, body.expense, body.notes, now),
    )
    await log_action(
        db,
        "updated",
        "finance_month",
        None,
        {"year_month": year_month, "income": body.income, "expense": body.expense},
    )
    await db.commit()
    return {
        "year_month": year_month,
        "manual_income": body.income,
        "manual_expense": body.expense,
        "notes": body.notes,
        "saved": True,
    }


@app.delete("/api/finance/months/{year_month}")
async def delete_finance_month(
    year_month: str,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    if not re.fullmatch(r"\d{4}-\d{2}", year_month):
        raise HTTPException(400, "year_month must be YYYY-MM")
    cur = await db.execute("SELECT year_month FROM finance_months WHERE year_month=?", (year_month,))
    if not await cur.fetchone():
        raise HTTPException(404, "Finance month not found")
    await db.execute("DELETE FROM finance_months WHERE year_month=?", (year_month,))
    await log_action(db, "deleted", "finance_month", None, {"year_month": year_month})
    await db.commit()
    return {"ok": True}


async def enrich_work_project(db: aiosqlite.Connection, project: dict[str, Any]) -> dict[str, Any]:
    pid = project["id"]
    cur = await db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS paid_sum FROM work_project_payments
        WHERE work_project_id=? AND COALESCE(status, 'received') = 'received'
        """,
        (pid,),
    )
    paid_sum = float((await cur.fetchone())["paid_sum"] or 0)
    cur = await db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS planned_sum FROM work_project_payments
        WHERE work_project_id=? AND status = 'planned'
        """,
        (pid,),
    )
    planned_sum = float((await cur.fetchone())["planned_sum"] or 0)
    cur = await db.execute(
        """
        SELECT * FROM work_project_payments
        WHERE work_project_id=?
        ORDER BY
          CASE COALESCE(status, 'received') WHEN 'planned' THEN 1 ELSE 0 END,
          paid_at DESC,
          id DESC
        """,
        (pid,),
    )
    payments = [row_to_dict(r) for r in await cur.fetchall()]
    return {**project, "paid_sum": paid_sum, "planned_sum": planned_sum, "payments": payments}


async def fetch_work_project(db: aiosqlite.Connection, item_id: int) -> dict[str, Any] | None:
    cur = await db.execute(
        "SELECT * FROM work_projects WHERE id=? AND deleted_at IS NULL",
        (item_id,),
    )
    row = row_to_dict(await cur.fetchone())
    if not row:
        return None
    return await enrich_work_project(db, row)


@app.get("/api/work-projects")
async def list_work_projects(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM work_projects WHERE deleted_at IS NULL ORDER BY "
        "CASE status WHEN 'active' THEN 0 WHEN 'paused' THEN 1 ELSE 2 END, updated_at DESC, id DESC"
    )
    rows = [row_to_dict(r) for r in await cur.fetchall()]
    return [await enrich_work_project(db, row) for row in rows]


@app.post("/api/work-projects")
async def create_work_project(
    body: WorkProjectIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO work_projects(title, status, client, budget, notes, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (body.title.strip(), body.status, body.client.strip(), body.budget, body.notes, now, now),
    )
    await log_action(db, "created", "work_project", cur.lastrowid, {"title": body.title})
    await db.commit()
    return await fetch_work_project(db, cur.lastrowid)


@app.patch("/api/work-projects/{item_id}")
async def patch_work_project(
    item_id: int,
    body: WorkProjectIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute("SELECT * FROM work_projects WHERE id=? AND deleted_at IS NULL", (item_id,))
    old = row_to_dict(await cur.fetchone())
    if not old:
        raise HTTPException(404, "Work project not found")
    await db.execute(
        """
        UPDATE work_projects SET title=?, status=?, client=?, budget=?, notes=?, updated_at=?
        WHERE id=?
        """,
        (body.title.strip(), body.status, body.client.strip(), body.budget, body.notes, utcnow(), item_id),
    )
    await log_action(db, "updated", "work_project", item_id, {"title": body.title})
    await db.commit()
    return await fetch_work_project(db, item_id)


@app.delete("/api/work-projects/{item_id}")
async def delete_work_project(
    item_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        "SELECT id, title FROM work_projects WHERE id=? AND deleted_at IS NULL",
        (item_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Work project not found")
    now = utcnow()
    await db.execute(
        "UPDATE work_projects SET deleted_at=?, updated_at=? WHERE id=? AND deleted_at IS NULL",
        (now, now, item_id),
    )
    await db.execute(
        "UPDATE tasks SET work_project_id=NULL, updated_at=? WHERE work_project_id=? AND deleted_at IS NULL",
        (now, item_id),
    )
    await db.execute("DELETE FROM work_project_payments WHERE work_project_id=?", (item_id,))
    await log_action(db, "deleted", "work_project", item_id, {"title": row["title"]})
    await db.commit()
    return {"ok": True}


@app.get("/api/work-projects/{item_id}/payments")
async def list_work_payments(
    item_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    project = await fetch_work_project(db, item_id)
    if not project:
        raise HTTPException(404, "Work project not found")
    return {
        "paid_sum": project["paid_sum"],
        "planned_sum": project["planned_sum"],
        "payments": project["payments"],
    }


@app.post("/api/work-projects/{item_id}/payments")
async def create_work_payment(
    item_id: int,
    body: WorkPaymentIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        "SELECT id FROM work_projects WHERE id=? AND deleted_at IS NULL",
        (item_id,),
    )
    if not await cur.fetchone():
        raise HTTPException(404, "Work project not found")
    now = utcnow()
    paid_at = (body.paid_at or "")[:32].strip() or now[:10]
    status = body.status if body.status in WORK_PAYMENT_STATUSES else "received"
    cur = await db.execute(
        """
        INSERT INTO work_project_payments(work_project_id, amount, paid_at, note, status, created_at)
        VALUES(?,?,?,?,?,?)
        """,
        (item_id, float(body.amount), paid_at, (body.note or "").strip()[:500], status, now),
    )
    payment_id = cur.lastrowid
    await log_action(
        db,
        "created",
        "work_payment",
        payment_id,
        {"work_project_id": item_id, "amount": body.amount},
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM work_project_payments WHERE id=?", (payment_id,))
    return row_to_dict(await cur.fetchone())


@app.patch("/api/work-projects/{item_id}/payments/{payment_id}")
async def patch_work_payment(
    item_id: int,
    payment_id: int,
    body: WorkPaymentPatch,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        """
        SELECT * FROM work_project_payments
        WHERE id=? AND work_project_id=?
        """,
        (payment_id, item_id),
    )
    old = row_to_dict(await cur.fetchone())
    if not old:
        raise HTTPException(404, "Payment not found")
    amount = float(body.amount) if body.amount is not None else float(old["amount"])
    paid_at = (body.paid_at or old["paid_at"] or "")[:32].strip() or utcnow()[:10]
    note = (body.note if body.note is not None else old.get("note") or "").strip()[:500]
    status = body.status if body.status in WORK_PAYMENT_STATUSES else old.get("status") or "received"
    next_work_project_id = item_id
    if body.work_project_id is not None and body.work_project_id != item_id:
        moved = await reassign_work_payment_project(
            db,
            payment_id=payment_id,
            from_work_project_id=item_id,
            to_work_project_id=body.work_project_id,
        )
        if not moved:
            raise HTTPException(404, "Work project not found")
        next_work_project_id = body.work_project_id
    await db.execute(
        """
        UPDATE work_project_payments SET amount=?, paid_at=?, note=?, status=?
        WHERE id=? AND work_project_id=?
        """,
        (amount, paid_at, note, status, payment_id, next_work_project_id),
    )
    await log_action(
        db,
        "updated",
        "work_payment",
        payment_id,
        {"work_project_id": next_work_project_id, "amount": amount, "status": status},
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM work_project_payments WHERE id=?", (payment_id,))
    return row_to_dict(await cur.fetchone())


@app.delete("/api/work-projects/{item_id}/payments/{payment_id}")
async def delete_work_payment(
    item_id: int,
    payment_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        """
        SELECT id, amount FROM work_project_payments
        WHERE id=? AND work_project_id=?
        """,
        (payment_id, item_id),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Payment not found")
    await db.execute("DELETE FROM work_project_payments WHERE id=?", (payment_id,))
    await log_action(
        db,
        "deleted",
        "work_payment",
        payment_id,
        {"work_project_id": item_id, "amount": row["amount"]},
    )
    await db.commit()
    return {"ok": True}


async def load_health_notes_map(db: aiosqlite.Connection) -> dict[str, list[dict[str, Any]]]:
    cur = await db.execute(
        "SELECT id, region, text, created_at FROM health_body_notes ORDER BY created_at DESC, id DESC"
    )
    notes: dict[str, list[dict[str, Any]]] = {}
    for raw in await cur.fetchall():
        row = row_to_dict(raw)
        notes.setdefault(row["region"], []).append(
            {"id": row["id"], "text": row["text"], "created_at": row["created_at"]}
        )
    return notes


@app.get("/api/health-profile")
async def get_health_profile(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute("SELECT * FROM health_metrics")
    metrics = {row_to_dict(r)["key"]: row_to_dict(r)["value"] for r in await cur.fetchall()}
    notes_map = await load_health_notes_map(db)
    cur = await db.execute("SELECT * FROM health_body")
    body = {}
    for r in await cur.fetchall():
        row = row_to_dict(r)
        region = row["region"]
        notes = notes_map.get(region, [])
        body[region] = {
            "note": notes[0]["text"] if notes else (row["note"] or ""),
            "status": normalize_health_status(row["status"]),
            "notes": notes,
        }
    defaults = {
        "weight": "",
        "height": "",
        "sleep": "",
        "pressure": "",
        "pulse": "",
        "mood": "",
    }
    for k, v in defaults.items():
        metrics.setdefault(k, v)
    for region in HEALTH_REGION_IDS:
        body.setdefault(region, {"note": "", "status": "ok", "notes": []})
    return {"metrics": metrics, "body": body}


@app.put("/api/health-profile")
async def put_health_profile(
    body: HealthProfileIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    for key, value in body.metrics.items():
        await db.execute(
            """
            INSERT INTO health_metrics(key, value, updated_at) VALUES(?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key[:32], str(value)[:200], now),
        )
    for region, data in body.body.items():
        region_id = region[:32]
        status = normalize_health_status(data.get("status"))
        cur = await db.execute("SELECT note FROM health_body WHERE region=?", (region_id,))
        old = await cur.fetchone()
        note = str(data["note"])[:500] if "note" in data else (row_to_dict(old)["note"] if old else "")
        await db.execute(
            """
            INSERT INTO health_body(region, note, status, updated_at) VALUES(?,?,?,?)
            ON CONFLICT(region) DO UPDATE SET
              note=excluded.note, status=excluded.status, updated_at=excluded.updated_at
            """,
            (region_id, note, status, now),
        )
        if "note" in data:
            text = str(data.get("note") or "").strip()[:2000]
            if text:
                cur = await db.execute(
                    "SELECT 1 FROM health_body_notes WHERE region=? LIMIT 1", (region_id,)
                )
                exists = await cur.fetchone()
                if not exists:
                    await db.execute(
                        "INSERT INTO health_body_notes(region, text, created_at) VALUES(?,?,?)",
                        (region_id, text, now),
                    )
    await log_action(db, "updated", "health_profile", None, {"metrics": list(body.metrics.keys())})
    await db.commit()
    return await get_health_profile(db, _)


@app.post("/api/health-body/{region}/notes")
async def add_health_note(
    region: str,
    body: HealthNoteIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    region_id = region[:32]
    if region_id not in HEALTH_REGION_IDS:
        raise HTTPException(status_code=404, detail="Unknown region")
    text = body.text.strip()[:2000]
    if not text:
        raise HTTPException(status_code=400, detail="Empty note")
    now = utcnow()
    await db.execute(
        """
        INSERT INTO health_body(region, note, status, updated_at) VALUES(?,?,?,?)
        ON CONFLICT(region) DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at
        """,
        (region_id, text, "ok", now),
    )
    cur = await db.execute(
        "INSERT INTO health_body_notes(region, text, created_at) VALUES(?,?,?)",
        (region_id, text, now),
    )
    await db.commit()
    return {"id": cur.lastrowid, "text": text, "created_at": now, "region": region_id}


@app.delete("/api/health-body/{region}/notes/{note_id}")
async def delete_health_note(
    region: str,
    note_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    region_id = region[:32]
    cur = await db.execute(
        "DELETE FROM health_body_notes WHERE id=? AND region=?",
        (note_id, region_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    cur = await db.execute(
        "SELECT text FROM health_body_notes WHERE region=? ORDER BY created_at DESC, id DESC LIMIT 1",
        (region_id,),
    )
    latest = await cur.fetchone()
    latest_text = row_to_dict(latest)["text"] if latest else ""
    await db.execute(
        "UPDATE health_body SET note=?, updated_at=? WHERE region=?",
        (latest_text, utcnow(), region_id),
    )
    await db.commit()
    return {"ok": True}


@app.get("/api/workout-panel")
async def workout_panel(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM workout_goals WHERE deleted_at IS NULL ORDER BY id DESC"
    )
    goals = [row_to_dict(r) for r in await cur.fetchall()]
    cur = await db.execute(
        """
        SELECT COUNT(*) AS c FROM workout_sessions
        WHERE deleted_at IS NULL AND started_at >= ?
        """,
        ((date.today() - timedelta(days=29)).isoformat(),),
    )
    workouts_30d = (await cur.fetchone())["c"]
    cur = await db.execute(
        """
        SELECT COUNT(*) AS c FROM workout_sessions
        WHERE deleted_at IS NULL AND started_at >= ?
        """,
        (date.today().isoformat(),),
    )
    workouts_today = (await cur.fetchone())["c"]
    cur = await db.execute(
        """
        SELECT ws.title, ws.started_at, COUNT(s.id) AS sets_count
        FROM workout_sessions ws
        LEFT JOIN workout_sets s ON s.session_id = ws.id
        WHERE ws.deleted_at IS NULL
        GROUP BY ws.id
        ORDER BY ws.started_at DESC
        LIMIT 8
        """
    )
    recent = [row_to_dict(r) for r in await cur.fetchall()]
    return {
        "goals": goals,
        "stats": {"workouts_30d": workouts_30d, "workouts_today": workouts_today},
        "recent": recent,
    }


@app.post("/api/workout-goals")
async def create_workout_goal(
    body: WorkoutGoalIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO workout_goals(title, target, unit, current, period, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (body.title.strip(), body.target, body.unit, body.current, body.period, now, now),
    )
    await log_action(db, "created", "workout_goal", cur.lastrowid, {"title": body.title})
    await db.commit()
    cur = await db.execute("SELECT * FROM workout_goals WHERE id=?", (cur.lastrowid,))
    return row_to_dict(await cur.fetchone())


@app.patch("/api/workout-goals/{goal_id}")
async def patch_workout_goal(
    goal_id: int,
    body: WorkoutGoalIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute("SELECT id FROM workout_goals WHERE id=? AND deleted_at IS NULL", (goal_id,))
    if not await cur.fetchone():
        raise HTTPException(404, "Goal not found")
    await db.execute(
        """
        UPDATE workout_goals SET title=?, target=?, unit=?, current=?, period=?, updated_at=?
        WHERE id=?
        """,
        (body.title.strip(), body.target, body.unit, body.current, body.period, utcnow(), goal_id),
    )
    await log_action(db, "updated", "workout_goal", goal_id, {"title": body.title})
    await db.commit()
    cur = await db.execute("SELECT * FROM workout_goals WHERE id=?", (goal_id,))
    return row_to_dict(await cur.fetchone())


@app.delete("/api/workout-goals/{goal_id}")
async def delete_workout_goal(
    goal_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    await db.execute(
        "UPDATE workout_goals SET deleted_at=?, updated_at=? WHERE id=? AND deleted_at IS NULL",
        (now, now, goal_id),
    )
    await log_action(db, "deleted", "workout_goal", goal_id, {})
    await db.commit()
    return {"ok": True}


@app.get("/api/backup")
async def backup(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    await log_action(db, "backup_exported", "system", None, {})
    await db.commit()
    tables = [
        "projects",
        "tasks",
        "notes",
        "workout_sessions",
        "workout_sets",
        "action_log",
        "daily_stats",
        "finance_months",
        "finance_categories",
        "finance_accounts",
        "finance_transactions",
        "finance_budget",
        "work_projects",
        "work_project_payments",
        "health_metrics",
        "health_body",
        "workout_goals",
    ]
    data: dict[str, Any] = {"exported_at": utcnow(), "tables": {}}
    for t in tables:
        cur = await db.execute(f"SELECT * FROM {t}")
        data["tables"][t] = [row_to_dict(r) for r in await cur.fetchall()]
    return data


@app.get("/widget")
async def widget_page():
    return FileResponse(STATIC / "widget.html")


@app.get("/capture")
async def capture_page():
    return FileResponse(
        STATIC / "capture.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


def _download_entries() -> list[dict[str, Any]]:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for item in DOWNLOAD_CATALOG:
        path = DOWNLOADS_DIR / item["filename"]
        available = path.is_file() and path.stat().st_size > 0
        entry = {
            **item,
            "available": available,
            "url": f"/downloads/{item['filename']}" if available else None,
            "size": path.stat().st_size if available else 0,
        }
        out.append(entry)
    return out


@app.get("/api/downloads")
async def list_downloads():
    return {"items": _download_entries()}


@app.api_route("/downloads/{filename}", methods=["GET", "HEAD"])
async def get_download(filename: str):
    # only catalog filenames
    allowed = {item["filename"] for item in DOWNLOAD_CATALOG}
    if filename not in allowed:
        raise HTTPException(404, "Unknown file")
    path = DOWNLOADS_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "File not ready yet")
    media = "application/vnd.android.package-archive" if filename.endswith(".apk") else "application/octet-stream"
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
        headers={
            "Cache-Control": "no-cache",
            "Accept-Ranges": "bytes",
        },
    )


@app.get("/download")
async def download_page():
    return FileResponse(STATIC / "download.html")


@app.get("/manifest.webmanifest")
async def web_manifest(request: Request):
    prefix = "/todo" if request.url.path.startswith("/todo") else ""
    # baski.pro/todo: Caddy handle_path strips prefix — detect via Referer
    referer = request.headers.get("referer", "")
    if not prefix and "/todo" in referer:
        prefix = "/todo"
    base = prefix or ""
    return JSONResponse(
        {
            "name": "NoteTask",
            "short_name": "NoteTask",
            "description": "Личные задачи, финансы и виджет на главном экране",
            "start_url": f"{base}/widget",
            "scope": f"{base}/" if base else "/",
            "display": "standalone",
            "background_color": "#f5f1e8",
            "theme_color": "#1f6b4e",
            "lang": "ru",
            "orientation": "portrait-primary",
            "icons": [
                {
                    "src": f"{base}/assets/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": f"{base}/assets/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
            "shortcuts": [
                {
                    "name": "Сегодня",
                    "url": f"{base}/widget",
                    "icons": [{"src": f"{base}/assets/icons/icon-192.png", "sizes": "192x192"}],
                },
                {
                    "name": "Добавить задачу",
                    "url": f"{base}/widget?add=1",
                    "icons": [{"src": f"{base}/assets/icons/icon-192.png", "sizes": "192x192"}],
                },
            ],
        },
        media_type="application/manifest+json",
    )


@app.get("/")
async def index():
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/{path:path}")
async def spa_fallback(path: str):
    # API 404s stay as API; everything else → SPA
    if path.startswith("api/"):
        raise HTTPException(404)
    candidate = STATIC / path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, reload=False)


if __name__ == "__main__":
    run()
