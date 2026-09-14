from __future__ import annotations

import aiosqlite

from .db import utcnow

UNCATEGORIZED_NAME = "Без раздела"
WORK_CATEGORY_NAME = "Работа"


def task_month_key(due_at: str | None, created_at: str | None) -> str | None:
    raw = (due_at or created_at or "").strip()
    if len(raw) < 7:
        return None
    return raw[:7]


async def get_or_create_category(db: aiosqlite.Connection, *, name: str, kind: str) -> int:
    clean = name.strip() or UNCATEGORIZED_NAME
    kind_n = "income" if kind == "income" else "expense"
    cur = await db.execute(
        """
        SELECT id FROM finance_categories
        WHERE deleted_at IS NULL AND name=? AND kind=?
        """,
        (clean, kind_n),
    )
    row = await cur.fetchone()
    if row:
        return int(row["id"])
    now = utcnow()
    group_name = "Доходы" if kind_n == "income" else "Расходы"
    cur = await db.execute(
        """
        INSERT INTO finance_categories(name, kind, group_name, sort, created_at, updated_at)
        VALUES(?,?,?,?,?,?)
        """,
        (clean, kind_n, group_name, 100, now, now),
    )
    await db.commit()
    return int(cur.lastrowid)


async def resolve_finance_category_id(
    db: aiosqlite.Connection,
    *,
    project_id: int | None,
    cost_type: str | None,
    finance_category_id: int | None = None,
    has_cost: bool,
) -> int | None:
    if finance_category_id:
        cur = await db.execute(
            "SELECT id FROM finance_categories WHERE id=? AND deleted_at IS NULL",
            (finance_category_id,),
        )
        row = await cur.fetchone()
        if row:
            return int(row["id"])
    if not has_cost:
        return None
    name = UNCATEGORIZED_NAME
    if project_id:
        cur = await db.execute(
            "SELECT name FROM projects WHERE id=? AND deleted_at IS NULL",
            (project_id,),
        )
        prow = await cur.fetchone()
        if prow and (prow["name"] or "").strip():
            name = str(prow["name"]).strip()
    return await get_or_create_category(db, name=name, kind=cost_type or "expense")


async def backfill_task_categories(db: aiosqlite.Connection) -> int:
    cur = await db.execute(
        """
        SELECT id, project_id, cost, cost_type, finance_category_id
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
          AND finance_category_id IS NULL
        """
    )
    rows = await cur.fetchall()
    n = 0
    for row in rows:
        cid = await resolve_finance_category_id(
            db,
            project_id=row["project_id"],
            cost_type=row["cost_type"],
            has_cost=True,
        )
        if cid is None:
            continue
        await db.execute(
            "UPDATE tasks SET finance_category_id=? WHERE id=?",
            (cid, row["id"]),
        )
        n += 1
    if n:
        await db.commit()
    return n
