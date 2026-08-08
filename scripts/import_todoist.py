#!/usr/bin/env python3
"""Import open (and optionally completed) tasks from Todoist API v1 into NoteTask."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import connect, ensure_defaults, log_action, migrate, utcnow

API_BASE = "https://api.todoist.com/api/v1"
SOURCE = "todoist"

TODOIST_COLORS = {
    "berry_red": "#b8255f",
    "red": "#db4035",
    "orange": "#ff9933",
    "yellow": "#fad000",
    "olive_green": "#afb83b",
    "lime_green": "#7ecc49",
    "green": "#299438",
    "mint_green": "#6accbc",
    "teal": "#158fad",
    "sky_blue": "#96c3eb",
    "light_blue": "#46a0f5",
    "blue": "#4073ff",
    "grape": "#884dff",
    "violet": "#af38eb",
    "lavender": "#eb96eb",
    "magenta": "#e05194",
    "salmon": "#ff8d85",
    "charcoal": "#808080",
    "grey": "#b8b8b8",
    "taupe": "#ccac93",
}


def fetch_page(token: str, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    url = f"{API_BASE}/{path}"
    if query:
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch_all(token: str, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page_params = dict(params or {})
        if cursor:
            page_params["cursor"] = cursor
        data = fetch_page(token, path, page_params)
        items.extend(data.get("results", data.get("items", [])))
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return items


def map_priority(todoist_priority: int | None) -> int:
    return max(1, min(4, 5 - int(todoist_priority or 1)))


def map_color(name: str | None) -> str:
    if not name:
        return "#2f6f4e"
    return TODOIST_COLORS.get(name, "#2f6f4e")


def parse_due(due: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not due:
        return None, None
    raw = due.get("date") or ""
    if not raw:
        return None, None
    if "T" in raw:
        iso = raw.replace("Z", "+00:00")
        if len(raw) == 16:
            iso = raw + ":00+00:00"
        return raw[:10], iso
    return raw[:10], None


def build_notes(
    *,
    description: str = "",
    section_name: str | None = None,
    labels: list[str] | None = None,
    parent_id: str | None = None,
    due: dict[str, Any] | None = None,
    deadline: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = []
    if description.strip():
        parts.append(description.strip())
    if section_name:
        parts.append(f"Секция: {section_name}")
    if labels:
        parts.append("Метки: " + ", ".join(labels))
    if parent_id:
        parts.append(f"Подзадача Todoist (parent): {parent_id}")
    if due and due.get("is_recurring") and due.get("string"):
        parts.append(f"Повтор: {due['string']}")
    if deadline and deadline.get("date"):
        parts.append(f"Дедлайн: {deadline['date']}")
    return "\n\n".join(parts)


async def find_project_by_external(db, external_id: str) -> int | None:
    cur = await db.execute(
        "SELECT id FROM projects WHERE source=? AND external_id=? AND deleted_at IS NULL",
        (SOURCE, external_id),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def find_inbox_project(db) -> int:
    cur = await db.execute(
        "SELECT id FROM projects WHERE deleted_at IS NULL AND lower(name)='inbox' ORDER BY id LIMIT 1"
    )
    row = await cur.fetchone()
    if row:
        return row[0]
    now = utcnow()
    cur = await db.execute(
        "INSERT INTO projects(name, color, sort, created_at, updated_at, source, external_id) "
        "VALUES(?,?,?,?,?,?,?)",
        ("Inbox", "#2f6f4e", 0, now, now, SOURCE, "inbox"),
    )
    return cur.lastrowid


async def upsert_project(db, project: dict[str, Any]) -> int:
    ext = project["id"]
    existing = await find_project_by_external(db, ext)
    name = project.get("name") or "Project"
    color = map_color(project.get("color"))
    now = utcnow()
    if existing:
        await db.execute(
            "UPDATE projects SET name=?, color=?, updated_at=? WHERE id=?",
            (name, color, now, existing),
        )
        return existing
    if project.get("inbox_project"):
        inbox_id = await find_inbox_project(db)
        await db.execute(
            "UPDATE projects SET source=?, external_id=?, color=?, updated_at=? WHERE id=?",
            (SOURCE, ext, color, now, inbox_id),
        )
        return inbox_id
    cur = await db.execute(
        "INSERT INTO projects(name, color, sort, created_at, updated_at, source, external_id) "
        "VALUES(?,?,?,?,?,?,?)",
        (name, color, int(project.get("child_order") or 99), now, now, SOURCE, ext),
    )
    return cur.lastrowid


async def task_exists(db, external_id: str) -> bool:
    cur = await db.execute(
        "SELECT id FROM tasks WHERE source=? AND external_id=? AND deleted_at IS NULL",
        (SOURCE, external_id),
    )
    return (await cur.fetchone()) is not None


async def insert_task(
    db,
    *,
    external_id: str,
    project_id: int | None,
    title: str,
    notes: str,
    priority: int,
    due_at: str | None,
    remind_at: str | None,
    status: str,
    completed_at: str | None,
    created_at: str,
) -> int | None:
    if await task_exists(db, external_id):
        return None
    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO tasks(
          project_id, title, notes, kind, priority, due_at, remind_at, status,
          created_at, updated_at, completed_at, source, external_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            project_id,
            title.strip() or "Без названия",
            notes,
            "task",
            priority,
            due_at,
            remind_at,
            status,
            created_at,
            now,
            completed_at,
            SOURCE,
            external_id,
        ),
    )
    tid = cur.lastrowid
    await log_action(
        db,
        "imported",
        "task",
        tid,
        {"source": SOURCE, "external_id": external_id, "title": title},
    )
    return tid


async def run_import(*, include_completed: bool) -> dict[str, int]:
    token = os.environ.get("TODOIST_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TODOIST_API_TOKEN in environment or .env")

    db = await connect()
    await ensure_defaults(db)

    projects = fetch_all(token, "projects")
    sections = fetch_all(token, "sections")
    open_tasks = [t for t in fetch_all(token, "tasks") if not t.get("checked") and not t.get("is_deleted")]

    sections_by_id = {s["id"]: s.get("name", "") for s in sections}
    project_map: dict[str, int] = {}
    for project in projects:
        if project.get("is_deleted") or project.get("is_archived"):
            continue
        pid = await upsert_project(db, project)
        project_map[project["id"]] = pid

    stats = {"projects": len(project_map), "open_imported": 0, "open_skipped": 0, "done_imported": 0, "done_skipped": 0}

    for task in open_tasks:
        ext = task["id"]
        project_id = project_map.get(task.get("project_id")) if task.get("project_id") else None
        due_day, remind_at = parse_due(task.get("due"))
        notes = build_notes(
            description=task.get("description") or "",
            section_name=sections_by_id.get(task.get("section_id") or ""),
            labels=task.get("labels") or [],
            parent_id=task.get("parent_id"),
            due=task.get("due"),
            deadline=task.get("deadline"),
        )
        title = task.get("content") or "Без названия"
        if task.get("parent_id"):
            title = f"↳ {title}"
        inserted = await insert_task(
            db,
            external_id=ext,
            project_id=project_id,
            title=title,
            notes=notes,
            priority=map_priority(task.get("priority")),
            due_at=due_day,
            remind_at=remind_at,
            status="open",
            completed_at=None,
            created_at=(task.get("added_at") or utcnow())[:19] + "+00:00",
        )
        if inserted:
            stats["open_imported"] += 1
        else:
            stats["open_skipped"] += 1

    if include_completed:
        completed = fetch_all(token, "tasks/completed", {"limit": "200"})
        for item in completed:
            ext = item.get("task_id") or item.get("id")
            if not ext:
                continue
            project_id = project_map.get(item.get("project_id")) if item.get("project_id") else None
            section_name = sections_by_id.get(item.get("section_id") or "")
            notes = build_notes(section_name=section_name or None)
            inserted = await insert_task(
                db,
                external_id=ext,
                project_id=project_id,
                title=item.get("content") or "Без названия",
                notes=notes,
                priority=4,
                due_at=None,
                remind_at=None,
                status="done",
                completed_at=item.get("completed_at"),
                created_at=(item.get("completed_at") or utcnow()),
            )
            if inserted:
                stats["done_imported"] += 1
            else:
                stats["done_skipped"] += 1

    await log_action(db, "todoist_import", "system", None, stats)
    await db.commit()
    await db.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Todoist data into NoteTask SQLite DB")
    parser.add_argument(
        "--completed",
        action="store_true",
        help="Also import completed tasks (may overlap skip if already imported as open)",
    )
    args = parser.parse_args()
    stats = asyncio.run(run_import(include_completed=args.completed))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
