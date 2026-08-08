from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import aiosqlite
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
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


# ---------- projects ----------

@app.get("/api/projects")
async def list_projects(db: aiosqlite.Connection = Depends(get_db), _: dict = Depends(require_auth)):
    cur = await db.execute(
        "SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY sort, id"
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


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
    cur = await db.execute(
        """
        INSERT INTO tasks(project_id, title, notes, kind, priority, due_at, remind_at, status, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?,'open',?,?)
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
    }
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
          status=?, completed_at=?, updated_at=? WHERE id=?
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
    return {
        "series": series,
        "streak": streak,
        "completions_30d": total_done,
        "workouts_30d": total_workouts,
        "open_tasks": open_tasks,
        "ideas": ideas,
    }


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
    ]
    data: dict[str, Any] = {"exported_at": utcnow(), "tables": {}}
    for t in tables:
        cur = await db.execute(f"SELECT * FROM {t}")
        data["tables"][t] = [row_to_dict(r) for r in await cur.fetchall()]
    return data


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
