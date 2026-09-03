from __future__ import annotations

import aiosqlite

WORK_PAYMENT_PLANNED_STATUSES = ("planned", "future")


async def work_payments_has_status(db: aiosqlite.Connection) -> bool:
    cur = await db.execute("PRAGMA table_info(work_project_payments)")
    return any(row[1] == "status" for row in await cur.fetchall())


def work_payment_received_filter(has_status: bool, alias: str = "p") -> str:
    if not has_status:
        return ""
    planned = ", ".join(f"'{s}'" for s in WORK_PAYMENT_PLANNED_STATUSES)
    return f" AND COALESCE({alias}.status, 'received') NOT IN ({planned})"


async def sum_work_payment_income(
    db: aiosqlite.Connection,
    *,
    year_month: str | None = None,
    since_day: str | None = None,
    year_months: list[str] | None = None,
) -> float | dict[str, float]:
    has_status = await work_payments_has_status(db)
    status_sql = work_payment_received_filter(has_status)
    base = f"""
        FROM work_project_payments p
        JOIN work_projects w ON w.id = p.work_project_id AND w.deleted_at IS NULL
        WHERE p.amount > 0{status_sql}
    """
    if year_month is not None:
        cur = await db.execute(
            f"SELECT COALESCE(SUM(p.amount), 0) AS total {base} AND SUBSTR(p.paid_at, 1, 7) = ?",
            (year_month,),
        )
        return float((await cur.fetchone())["total"] or 0)
    if since_day is not None:
        cur = await db.execute(
            f"SELECT COALESCE(SUM(p.amount), 0) AS total {base} AND SUBSTR(p.paid_at, 1, 10) >= ?",
            (since_day,),
        )
        return float((await cur.fetchone())["total"] or 0)
    if year_months:
        placeholders = ",".join("?" * len(year_months))
        cur = await db.execute(
            f"""
            SELECT SUBSTR(p.paid_at, 1, 7) AS ym, COALESCE(SUM(p.amount), 0) AS total
            {base} AND SUBSTR(p.paid_at, 1, 7) IN ({placeholders})
            GROUP BY ym
            """,
            year_months,
        )
        return {row["ym"]: float(row["total"] or 0) for row in await cur.fetchall()}
    return 0.0
