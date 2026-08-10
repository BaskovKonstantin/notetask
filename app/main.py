from __future__ import annotations

import json
import re
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
from .config import PORT
from .db import (
    bump_completions,
    bump_workouts,
    connect,
    ensure_defaults,
    log_action,
    row_to_dict,
    utcnow,
)

STATIC = Path(__file__).resolve().parents[1] / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await connect()
    await ensure_defaults(db)
    app.state.db = db
    yield
    await db.close()


app = FastAPI(title="NoteTask", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


async def get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db


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
    remind_at: str | None = None
    project_id: int | None = None
    status: Literal["open", "done"] | None = None
    location: str | None = None
    cost: float | None = None
    cost_type: Literal["expense", "income"] | None = None
    work_project_id: int | None = None


class TaskPatchIn(BaseModel):
    title: str | None = None
    notes: str | None = None
    kind: Literal["task", "idea", "plan"] | None = None
    priority: int | None = Field(default=None, ge=1, le=4)
    due_at: str | None = None
    remind_at: str | None = None
    project_id: int | None = None
    status: Literal["open", "done"] | None = None
    location: str | None = None
    cost: float | None = None
    cost_type: Literal["expense", "income"] | None = None
    work_project_id: int | None = None


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


class WorkoutIn(BaseModel):
    title: str = "Тренировка"
    notes: str = ""
    started_at: str | None = None
    sets: list[WorkoutSetIn] = Field(default_factory=list)


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


class HealthProfileIn(BaseModel):
    metrics: dict[str, str] = Field(default_factory=dict)
    body: dict[str, dict[str, str]] = Field(default_factory=dict)


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
    today = date.today().isoformat()
    if view == "today":
        return [
            t
            for t in rows
            if t["kind"] == "task"
            and t["due_at"]
            and t["due_at"][:10] <= today
        ]
    if view == "upcoming":
        return [
            t
            for t in rows
            if t["kind"] == "task" and t["due_at"] and t["due_at"][:10] > today
        ]
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
    cur = await db.execute(
        """
        INSERT INTO tasks(
          project_id, title, notes, kind, priority, due_at, remind_at,
          status, created_at, updated_at, location, cost, cost_type, work_project_id
        )
        VALUES(?,?,?,?,?,?,?,'open',?,?,?,?,?,?)
        """,
        (
            body.project_id,
            body.title.strip(),
            body.notes,
            body.kind,
            body.priority,
            body.due_at,
            body.remind_at,
            now,
            now,
            body.location,
            body.cost,
            body.cost_type,
            work_project_id,
        ),
    )
    tid = cur.lastrowid
    await log_action(
        db,
        "created",
        "task",
        tid,
        {"title": body.title, "kind": body.kind, "due_at": body.due_at},
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

    await db.execute(
        """
        UPDATE tasks SET project_id=?, title=?, notes=?, kind=?, priority=?, due_at=?, remind_at=?,
          status=?, completed_at=?, updated_at=?, location=?, cost=?, cost_type=?, work_project_id=?
        WHERE id=?
        """,
        (
            next_values["project_id"],
            next_values["title"],
            next_values["notes"],
            next_values["kind"],
            next_values["priority"],
            next_values["due_at"],
            next_values["remind_at"],
            status,
            completed_at,
            utcnow(),
            next_values.get("location"),
            next_values.get("cost"),
            next_values.get("cost_type"),
            next_values.get("work_project_id"),
            task_id,
        ),
    )
    await db.commit()
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
    next_values = {
        "project_id": body.project_id,
        "title": body.title.strip(),
        "notes": body.notes,
        "kind": body.kind,
        "priority": body.priority,
        "due_at": body.due_at,
        "remind_at": body.remind_at,
        "status": status,
        "location": body.location,
        "cost": body.cost,
        "cost_type": body.cost_type,
        "work_project_id": body.work_project_id,
    }
    next_values["work_project_id"] = await normalize_work_project_id(
        db, next_values.get("project_id"), next_values.get("work_project_id")
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
        UPDATE tasks SET project_id=?, title=?, notes=?, kind=?, priority=?, due_at=?, remind_at=?,
          status=?, completed_at=?, updated_at=?, location=?, cost=?, cost_type=?, work_project_id=?
        WHERE id=?
        """,
        (
            next_values["project_id"],
            next_values["title"],
            next_values["notes"],
            next_values["kind"],
            next_values["priority"],
            next_values["due_at"],
            next_values["remind_at"],
            status,
            completed_at,
            utcnow(),
            next_values["location"],
            next_values["cost"],
            next_values["cost_type"],
            next_values["work_project_id"],
            task_id,
        ),
    )
    await db.commit()
    return await fetch_task(db, task_id)


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(
    task_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    old = await fetch_task(db, task_id)
    if old["status"] == "done":
        return old
    now = utcnow()
    await db.execute(
        "UPDATE tasks SET status='done', completed_at=?, updated_at=? WHERE id=?",
        (now, now, task_id),
    )
    await bump_completions(db)
    await log_action(db, "completed", "task", task_id, {"title": old["title"]})
    await db.commit()
    return await fetch_task(db, task_id)


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
        "INSERT INTO workout_sessions(title, notes, started_at, created_at, updated_at) VALUES(?,?,?,?,?)",
        (body.title.strip() or "Тренировка", body.notes, started, now, now),
    )
    sid = cur.lastrowid
    for s in body.sets:
        await db.execute(
            """
            INSERT INTO workout_sets(session_id, exercise, weight, reps, set_index, notes)
            VALUES(?,?,?,?,?,?)
            """,
            (sid, s.exercise.strip(), s.weight, s.reps, s.set_index, s.notes),
        )
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
    out = []
    for ym in keys:
        row = saved.get(ym) or {"year_month": ym, "income": 0, "expense": 0, "notes": ""}
        task_totals = from_tasks.get(ym, {"expense": 0.0, "income": 0.0})
        income = float(row.get("income") or 0)
        expense = float(row.get("expense") or 0)
        out.append(
            {
                "year_month": ym,
                "income": income,
                "expense": expense,
                "notes": row.get("notes") or "",
                "balance": income - expense,
                "task_income": task_totals["income"],
                "task_expense": task_totals["expense"],
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
        },
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
        "income": body.income,
        "expense": body.expense,
        "notes": body.notes,
        "balance": body.income - body.expense,
    }


@app.get("/api/work-projects")
async def list_work_projects(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM work_projects WHERE deleted_at IS NULL ORDER BY "
        "CASE status WHEN 'active' THEN 0 WHEN 'paused' THEN 1 ELSE 2 END, updated_at DESC, id DESC"
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


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
    cur = await db.execute("SELECT * FROM work_projects WHERE id=?", (cur.lastrowid,))
    return row_to_dict(await cur.fetchone())


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
    cur = await db.execute("SELECT * FROM work_projects WHERE id=?", (item_id,))
    return row_to_dict(await cur.fetchone())


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
    await log_action(db, "deleted", "work_project", item_id, {"title": row["title"]})
    await db.commit()
    return {"ok": True}


@app.get("/api/health-profile")
async def get_health_profile(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute("SELECT * FROM health_metrics")
    metrics = {row_to_dict(r)["key"]: row_to_dict(r)["value"] for r in await cur.fetchall()}
    cur = await db.execute("SELECT * FROM health_body")
    body = {
        row_to_dict(r)["region"]: {"note": row_to_dict(r)["note"], "status": row_to_dict(r)["status"]}
        for r in await cur.fetchall()
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
    for region in ("head", "chest", "arms", "stomach", "back", "legs"):
        body.setdefault(region, {"note": "", "status": "ok"})
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
        await db.execute(
            """
            INSERT INTO health_body(region, note, status, updated_at) VALUES(?,?,?,?)
            ON CONFLICT(region) DO UPDATE SET
              note=excluded.note, status=excluded.status, updated_at=excluded.updated_at
            """,
            (
                region[:32],
                str(data.get("note") or "")[:500],
                str(data.get("status") or "ok")[:16],
                now,
            ),
        )
    await log_action(db, "updated", "health_profile", None, {"metrics": list(body.metrics.keys())})
    await db.commit()
    cur = await db.execute("SELECT * FROM health_metrics")
    metrics = {row_to_dict(r)["key"]: row_to_dict(r)["value"] for r in await cur.fetchall()}
    cur = await db.execute("SELECT * FROM health_body")
    regions = {
        row_to_dict(r)["region"]: {"note": row_to_dict(r)["note"], "status": row_to_dict(r)["status"]}
        for r in await cur.fetchall()
    }
    return {"metrics": metrics, "body": regions}


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
        "work_projects",
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
    return FileResponse(STATIC / "index.html")


@app.get("/{path:path}")
async def spa_fallback(path: str):
    # API 404s stay as API; everything else → SPA
    if path.startswith("api/"):
        raise HTTPException(404)
    candidate = STATIC / path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC / "index.html")


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, reload=False)


if __name__ == "__main__":
    run()
