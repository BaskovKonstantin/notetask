from __future__ import annotations

from typing import Any

import aiosqlite

from .finance_task_sync import UNCATEGORIZED_NAME

WORK_SECTION_NAME = "Работа"


def _day10(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if len(text) < 10:
        return None
    return text[:10]


def _task_amount(cost: Any, cost_type: str | None) -> float:
    value = float(cost or 0)
    if cost_type == "income":
        return value
    return -abs(value)


def _row_status(*, is_task: bool, raw: str | None) -> str:
    if is_task:
        return "confirmed" if raw == "done" else "plan"
    return "plan" if raw == "planned" else "confirmed"


async def list_finance_ledger_rows(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute(
        """
        SELECT t.id, t.project_id, t.title, t.status, t.due_at, t.cost, t.cost_type,
               p.name AS project_name
        FROM tasks t
        LEFT JOIN projects p ON p.id = t.project_id AND p.deleted_at IS NULL
        WHERE t.deleted_at IS NULL AND t.cost IS NOT NULL AND t.cost != 0
        """
    )
    task_rows = []
    for row in await cur.fetchall():
        name = (row["project_name"] or "").strip() or UNCATEGORIZED_NAME
        task_rows.append(
            {
                "source": "task",
                "id": int(row["id"]),
                "project_id": row["project_id"],
                "project_name": name,
                "title": row["title"] or "",
                "amount": _task_amount(row["cost"], row["cost_type"]),
                "day": _day10(row["due_at"]),
                "status": _row_status(is_task=True, raw=row["status"]),
            }
        )

    cur = await db.execute(
        """
        SELECT p.id AS payment_id, p.work_project_id, p.amount, p.paid_at, p.status,
               w.title AS work_title, sec.id AS work_section_id
        FROM work_project_payments p
        JOIN work_projects w ON w.id = p.work_project_id AND w.deleted_at IS NULL
        LEFT JOIN (
          SELECT id FROM projects WHERE deleted_at IS NULL AND name = ? ORDER BY id LIMIT 1
        ) sec ON 1=1
        """,
        (WORK_SECTION_NAME,),
    )
    work_rows = []
    for row in await cur.fetchall():
        work_rows.append(
            {
                "source": "work",
                "id": int(row["payment_id"]),
                "project_id": row["work_section_id"],
                "project_name": WORK_SECTION_NAME,
                "title": row["work_title"] or "",
                "amount": float(row["amount"] or 0),
                "day": _day10(row["paid_at"]),
                "status": _row_status(is_task=False, raw=row["status"]),
                "work_project_id": int(row["work_project_id"]),
            }
        )

    rows = task_rows + work_rows
    dated = [r for r in rows if r.get("day")]
    undated = [r for r in rows if not r.get("day")]
    dated.sort(key=lambda r: (r["day"], r["source"], r["id"]), reverse=True)
    undated.sort(key=lambda r: (r["source"], r["id"]), reverse=True)
    return dated + undated
