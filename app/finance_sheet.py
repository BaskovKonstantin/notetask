"""Dedicated finance sheet: categories, accounts, budget, transactions."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import require_auth
from .db import log_action, row_to_dict, utcnow
from .deps import get_db
from .finance_helpers import (
    sum_work_payment_income,
    work_payment_received_filter,
    work_payments_has_status,
)
from .finance_task_sync import (
    WORK_CATEGORY_NAME,
    backfill_task_categories,
    get_or_create_category,
    task_month_key,
)

router = APIRouter(prefix="/api/finance", tags=["finance-sheet"])

DEFAULT_CATEGORIES: list[tuple[str, str, str, int]] = [
    ("Зарплата", "income", "Доходы", 0),
    ("Подработка", "income", "Доходы", 1),
    ("Прочие доходы", "income", "Доходы", 2),
    ("ЖКХ", "expense", "Обязательные", 10),
    ("Связь и интернет", "expense", "Обязательные", 11),
    ("Кредиты", "expense", "Обязательные", 12),
    ("Страховка", "expense", "Обязательные", 13),
    ("Продукты", "expense", "Быт", 20),
    ("Бытовая химия", "expense", "Быт", 21),
    ("Транспорт", "expense", "Быт", 22),
    ("Бензин", "expense", "Быт", 23),
    ("Кафе и рестораны", "expense", "Досуг", 30),
    ("Подписки", "expense", "Досуг", 31),
    ("Развлечения", "expense", "Досуг", 32),
    ("Одежда", "expense", "Досуг", 33),
    ("Здоровье", "expense", "Прочее", 40),
    ("Образование", "expense", "Прочее", 41),
    ("Подарки", "expense", "Прочее", 42),
    ("Прочие расходы", "expense", "Прочее", 43),
    ("Накопления", "expense", "Накопления", 50),
    ("Крупные покупки", "expense", "Накопления", 51),
]

DEFAULT_ACCOUNTS: list[tuple[str, int, float]] = [
    ("Наличные", 0, 0),
    ("Дебетовая карта", 1, 0),
    ("Накопительный счёт", 2, 0),
]


class FinanceCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["expense", "income"] = "expense"
    group_name: str = ""
    sort: int = 0


class FinanceAccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    opening_balance: float = 0
    sort: int = 0


class FinanceTransactionIn(BaseModel):
    category_id: int | None = None
    account_id: int | None = None
    kind: Literal["expense", "income"] = "expense"
    amount: float = Field(gt=0)
    day: str
    note: str = ""


class FinanceTransactionPatch(BaseModel):
    category_id: int | None = None
    account_id: int | None = None
    kind: Literal["expense", "income"] | None = None
    amount: float | None = Field(default=None, gt=0)
    day: str | None = None
    note: str | None = None


class FinanceBudgetIn(BaseModel):
    planned: float = 0


class FinanceImportIn(BaseModel):
    csv_text: str
    year_month: str | None = None


def _validate_year_month(year_month: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}", year_month):
        raise HTTPException(400, "year_month must be YYYY-MM")


async def ensure_finance_sheet_defaults(db: aiosqlite.Connection) -> None:
    cur = await db.execute(
        "SELECT COUNT(*) AS n FROM finance_categories WHERE deleted_at IS NULL"
    )
    if int((await cur.fetchone())["n"]) == 0:
        now = utcnow()
        for name, kind, group_name, sort in DEFAULT_CATEGORIES:
            await db.execute(
                """
                INSERT INTO finance_categories(name, kind, group_name, sort, created_at, updated_at)
                VALUES(?,?,?,?,?,?)
                """,
                (name, kind, group_name, sort, now, now),
            )
    cur = await db.execute(
        "SELECT COUNT(*) AS n FROM finance_accounts WHERE deleted_at IS NULL"
    )
    if int((await cur.fetchone())["n"]) == 0:
        now = utcnow()
        for name, sort, opening in DEFAULT_ACCOUNTS:
            await db.execute(
                """
                INSERT INTO finance_accounts(name, sort, opening_balance, created_at, updated_at)
                VALUES(?,?,?,?,?)
                """,
                (name, sort, opening, now, now),
            )
    await db.commit()


async def category_has_entries(db: aiosqlite.Connection, category_id: int) -> bool:
    cur = await db.execute(
        "SELECT 1 FROM tasks WHERE deleted_at IS NULL AND finance_category_id=? AND cost IS NOT NULL AND cost != 0 LIMIT 1",
        (category_id,),
    )
    if await cur.fetchone():
        return True
    cur = await db.execute(
        "SELECT 1 FROM finance_transactions WHERE deleted_at IS NULL AND category_id=? LIMIT 1",
        (category_id,),
    )
    if await cur.fetchone():
        return True
    cur = await db.execute(
        "SELECT name, kind FROM finance_categories WHERE id=?",
        (category_id,),
    )
    row = await cur.fetchone()
    if row and row["name"] == WORK_CATEGORY_NAME and row["kind"] == "income":
        cur = await db.execute(
            """
            SELECT 1 FROM work_project_payments p
            JOIN work_projects w ON w.id = p.work_project_id AND w.deleted_at IS NULL
            WHERE p.amount > 0 LIMIT 1
            """
        )
        return await cur.fetchone() is not None
    return False


async def assert_unique_live_category(
    db: aiosqlite.Connection,
    name: str,
    kind: str,
    exclude_id: int | None = None,
) -> None:
    params: list[Any] = [name.strip(), kind]
    sql = """
        SELECT id FROM finance_categories
        WHERE deleted_at IS NULL AND name=? AND kind=?
    """
    if exclude_id is not None:
        sql += " AND id!=?"
        params.append(exclude_id)
    cur = await db.execute(sql, params)
    if await cur.fetchone():
        raise HTTPException(409, "Category already exists")


async def category_actuals_for_month(
    db: aiosqlite.Connection, year_month: str
) -> dict[int, list[dict]]:
    by_cat: dict[int, list[dict]] = {}

    def add(cid: int | None, entry: dict) -> None:
        if cid is None:
            return
        by_cat.setdefault(int(cid), []).append(entry)

    cur = await db.execute(
        """
        SELECT t.id, t.category_id, t.amount, t.day, t.note, c.name AS category_name
        FROM finance_transactions t
        LEFT JOIN finance_categories c ON c.id = t.category_id
        WHERE t.deleted_at IS NULL AND SUBSTR(t.day, 1, 7) = ?
        """,
        (year_month,),
    )
    for row in await cur.fetchall():
        d = row_to_dict(row)
        title = d.get("note") or d.get("category_name") or "Операция"
        add(
            d.get("category_id"),
            {
                "source": "sheet",
                "id": d["id"],
                "title": title,
                "amount": float(d["amount"] or 0),
                "day": d["day"][:10] if d.get("day") else None,
                "task_id": None,
            },
        )

    cur = await db.execute(
        """
        SELECT id, title, cost, due_at, created_at, finance_category_id
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
        """
    )
    for row in await cur.fetchall():
        d = row_to_dict(row)
        if task_month_key(d.get("due_at"), d.get("created_at")) != year_month:
            continue
        day_raw = d.get("due_at") or d.get("created_at")
        add(
            d.get("finance_category_id"),
            {
                "source": "task",
                "id": d["id"],
                "title": d["title"] or "Задача",
                "amount": float(d["cost"] or 0),
                "day": str(day_raw)[:10] if day_raw else None,
                "task_id": d["id"],
            },
        )

    work_cat_id = await get_or_create_category(db, name=WORK_CATEGORY_NAME, kind="income")
    has_status = await work_payments_has_status(db)
    status_sql = work_payment_received_filter(has_status, alias="p")
    cur = await db.execute(
        f"""
        SELECT p.id, p.amount, p.paid_at, p.note, w.title AS project_title
        FROM work_project_payments p
        JOIN work_projects w ON w.id = p.work_project_id AND w.deleted_at IS NULL
        WHERE p.amount > 0{status_sql}
          AND SUBSTR(p.paid_at, 1, 7) = ?
        """,
        (year_month,),
    )
    for row in await cur.fetchall():
        d = row_to_dict(row)
        note = (d.get("note") or "").strip()
        title = f"{d['project_title']}: {note}" if note else str(d["project_title"])
        add(
            work_cat_id,
            {
                "source": "work",
                "id": d["id"],
                "title": title,
                "amount": float(d["amount"] or 0),
                "day": str(d["paid_at"])[:10] if d.get("paid_at") else None,
                "task_id": None,
            },
        )
    return by_cat


async def _task_totals_for_month(db: aiosqlite.Connection, year_month: str) -> tuple[float, float]:
    day_expr = "COALESCE(NULLIF(TRIM(due_at), ''), created_at)"
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
    return task_income, task_expense


async def _merged_entries(db: aiosqlite.Connection, year_month: str) -> list[dict[str, Any]]:
    day_expr = "COALESCE(NULLIF(TRIM(due_at), ''), created_at)"
    entries: list[dict[str, Any]] = []

    cur = await db.execute(
        """
        SELECT t.id, t.kind, t.amount, t.day, t.note,
               c.name AS category_name, a.name AS account_name
        FROM finance_transactions t
        LEFT JOIN finance_categories c ON c.id = t.category_id
        LEFT JOIN finance_accounts a ON a.id = t.account_id
        WHERE t.deleted_at IS NULL AND SUBSTR(t.day, 1, 7) = ?
        ORDER BY t.day DESC, t.id DESC
        """,
        (year_month,),
    )
    for row in await cur.fetchall():
        d = row_to_dict(row)
        title = d.get("note") or d.get("category_name") or "Операция"
        entries.append(
            {
                "id": d["id"],
                "entry_type": "transaction",
                "title": title,
                "cost": float(d["amount"] or 0),
                "cost_type": d["kind"],
                "day": d["day"][:10] if d.get("day") else None,
                "category_name": d.get("category_name"),
                "account_name": d.get("account_name"),
                "source": "sheet",
            }
        )

    cur = await db.execute(
        f"""
        SELECT id, title, cost, cost_type, due_at, created_at
        FROM tasks
        WHERE deleted_at IS NULL AND cost IS NOT NULL AND cost != 0
          AND SUBSTR({day_expr},1,7) = ?
        ORDER BY {day_expr} DESC, id DESC
        LIMIT 100
        """,
        (year_month,),
    )
    for row in await cur.fetchall():
        d = row_to_dict(row)
        day_raw = d.get("due_at") or d.get("created_at")
        day = str(day_raw)[:10] if day_raw else None
        entries.append(
            {
                "id": d["id"],
                "entry_type": "task",
                "title": d["title"] or "Задача",
                "cost": float(d["cost"] or 0),
                "cost_type": d["cost_type"] or "expense",
                "day": day,
                "source": "task",
            }
        )

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
                "source": "work",
            }
        )

    entries.sort(key=lambda e: (e.get("day") or "", e.get("id") or 0), reverse=True)
    return entries


@router.get("/sheet")
async def get_finance_sheet(
    year_month: str | None = None,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    ym = year_month or utcnow()[:7]
    _validate_year_month(ym)
    await ensure_finance_sheet_defaults(db)
    await backfill_task_categories(db)
    await get_or_create_category(db, name=WORK_CATEGORY_NAME, kind="income")

    cur = await db.execute(
        """
        SELECT * FROM finance_categories
        WHERE deleted_at IS NULL
        ORDER BY kind DESC, group_name, sort, name
        """
    )
    categories = [row_to_dict(r) for r in await cur.fetchall()]

    cur = await db.execute(
        """
        SELECT * FROM finance_accounts
        WHERE deleted_at IS NULL
        ORDER BY sort, name
        """
    )
    accounts = [row_to_dict(r) for r in await cur.fetchall()]

    cur = await db.execute(
        "SELECT category_id, planned FROM finance_budget WHERE year_month=?",
        (ym,),
    )
    planned_by_cat = {row["category_id"]: float(row["planned"] or 0) for row in await cur.fetchall()}

    cur = await db.execute(
        """
        SELECT account_id,
               SUM(CASE WHEN kind='income' THEN amount ELSE -amount END) AS delta
        FROM finance_transactions
        WHERE deleted_at IS NULL AND SUBSTR(day, 1, 7) <= ?
        GROUP BY account_id
        """,
        (ym,),
    )
    account_deltas = {row["account_id"]: float(row["delta"] or 0) for row in await cur.fetchall()}
    account_rows = []
    for acc in accounts:
        aid = acc["id"]
        balance = float(acc["opening_balance"] or 0) + account_deltas.get(aid, 0)
        account_rows.append({**acc, "balance": balance})

    cur = await db.execute(
        """
        SELECT kind, SUM(amount) AS total
        FROM finance_transactions
        WHERE deleted_at IS NULL AND SUBSTR(day, 1, 7) = ?
        GROUP BY kind
        """,
        (ym,),
    )
    tx_income = 0.0
    tx_expense = 0.0
    for row in await cur.fetchall():
        if row["kind"] == "income":
            tx_income = float(row["total"] or 0)
        else:
            tx_expense = float(row["total"] or 0)

    task_income, task_expense = await _task_totals_for_month(db, ym)
    work_income = float(await sum_work_payment_income(db, year_month=ym))

    income = tx_income + task_income + work_income
    expense = tx_expense + task_expense

    actuals = await category_actuals_for_month(db, ym)
    budget_rows = []
    for cat in categories:
        cid = cat["id"]
        kind = cat["kind"]
        fact_entries = list(actuals.get(cid, []))
        actual = sum(float(e.get("amount") or 0) for e in fact_entries)
        planned = planned_by_cat.get(cid, 0)
        budget_rows.append(
            {
                **cat,
                "planned": planned,
                "actual": actual,
                "delta": planned - actual if kind == "expense" else actual - planned,
                "fact_entries": fact_entries,
            }
        )

    entries = await _merged_entries(db, ym)

    cur = await db.execute(
        "SELECT notes FROM finance_months WHERE year_month=?",
        (ym,),
    )
    saved = await cur.fetchone()
    notes = (saved["notes"] if saved else "") or ""

    return {
        "year_month": ym,
        "summary": {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "transaction_income": tx_income,
            "transaction_expense": tx_expense,
            "task_income": task_income,
            "task_expense": task_expense,
            "work_income": work_income,
        },
        "categories": budget_rows,
        "accounts": account_rows,
        "entries": entries,
        "notes": notes,
    }


@router.get("/categories")
async def list_finance_categories(
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await ensure_finance_sheet_defaults(db)
    cur = await db.execute(
        """
        SELECT * FROM finance_categories
        WHERE deleted_at IS NULL
        ORDER BY kind DESC, group_name, sort, name
        """
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


@router.post("/categories")
async def create_finance_category(
    body: FinanceCategoryIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await assert_unique_live_category(db, body.name, body.kind)
    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO finance_categories(name, kind, group_name, sort, created_at, updated_at)
        VALUES(?,?,?,?,?,?)
        """,
        (body.name.strip(), body.kind, body.group_name.strip(), body.sort, now, now),
    )
    await log_action(db, "created", "finance_category", cur.lastrowid, {"name": body.name})
    await db.commit()
    cur = await db.execute("SELECT * FROM finance_categories WHERE id=?", (cur.lastrowid,))
    return row_to_dict(await cur.fetchone())


@router.patch("/categories/{category_id}")
async def patch_finance_category(
    category_id: int,
    body: FinanceCategoryIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await assert_unique_live_category(
        db, body.name, body.kind, exclude_id=category_id
    )
    now = utcnow()
    cur = await db.execute(
        """
        UPDATE finance_categories
        SET name=?, kind=?, group_name=?, sort=?, updated_at=?
        WHERE id=? AND deleted_at IS NULL
        """,
        (body.name.strip(), body.kind, body.group_name.strip(), body.sort, now, category_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Category not found")
    await log_action(db, "updated", "finance_category", category_id, {"name": body.name})
    await db.commit()
    cur = await db.execute("SELECT * FROM finance_categories WHERE id=?", (category_id,))
    return row_to_dict(await cur.fetchone())


@router.delete("/categories/{category_id}")
async def delete_finance_category(
    category_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        "SELECT id FROM finance_categories WHERE id=? AND deleted_at IS NULL",
        (category_id,),
    )
    if not await cur.fetchone():
        raise HTTPException(404, "Category not found")
    if await category_has_entries(db, category_id):
        raise HTTPException(409, "Category has entries")
    now = utcnow()
    cur = await db.execute(
        "UPDATE finance_categories SET deleted_at=?, updated_at=? WHERE id=? AND deleted_at IS NULL",
        (now, now, category_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Category not found")
    await log_action(db, "deleted", "finance_category", category_id, {})
    await db.commit()
    return {"ok": True}


@router.get("/accounts")
async def list_finance_accounts(
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    await ensure_finance_sheet_defaults(db)
    cur = await db.execute(
        "SELECT * FROM finance_accounts WHERE deleted_at IS NULL ORDER BY sort, name"
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


@router.post("/accounts")
async def create_finance_account(
    body: FinanceAccountIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO finance_accounts(name, sort, opening_balance, created_at, updated_at)
        VALUES(?,?,?,?,?)
        """,
        (body.name.strip(), body.sort, body.opening_balance, now, now),
    )
    await log_action(db, "created", "finance_account", cur.lastrowid, {"name": body.name})
    await db.commit()
    cur = await db.execute("SELECT * FROM finance_accounts WHERE id=?", (cur.lastrowid,))
    return row_to_dict(await cur.fetchone())


@router.patch("/accounts/{account_id}")
async def patch_finance_account(
    account_id: int,
    body: FinanceAccountIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        """
        UPDATE finance_accounts
        SET name=?, sort=?, opening_balance=?, updated_at=?
        WHERE id=? AND deleted_at IS NULL
        """,
        (body.name.strip(), body.sort, body.opening_balance, now, account_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Account not found")
    await log_action(db, "updated", "finance_account", account_id, {"name": body.name})
    await db.commit()
    cur = await db.execute("SELECT * FROM finance_accounts WHERE id=?", (account_id,))
    return row_to_dict(await cur.fetchone())


@router.delete("/accounts/{account_id}")
async def delete_finance_account(
    account_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        "UPDATE finance_accounts SET deleted_at=?, updated_at=? WHERE id=? AND deleted_at IS NULL",
        (now, now, account_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Account not found")
    await log_action(db, "deleted", "finance_account", account_id, {})
    await db.commit()
    return {"ok": True}


@router.post("/transactions")
async def create_finance_transaction(
    body: FinanceTransactionIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", body.day[:10]):
        raise HTTPException(400, "day must be YYYY-MM-DD")
    now = utcnow()
    cur = await db.execute(
        """
        INSERT INTO finance_transactions(
          category_id, account_id, kind, amount, day, note, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            body.category_id,
            body.account_id,
            body.kind,
            body.amount,
            body.day[:10],
            body.note.strip(),
            now,
            now,
        ),
    )
    await log_action(
        db,
        "created",
        "finance_transaction",
        cur.lastrowid,
        {"amount": body.amount, "kind": body.kind},
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM finance_transactions WHERE id=?", (cur.lastrowid,))
    return row_to_dict(await cur.fetchone())


@router.patch("/transactions/{transaction_id}")
async def patch_finance_transaction(
    transaction_id: int,
    body: FinanceTransactionPatch,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    cur = await db.execute(
        "SELECT * FROM finance_transactions WHERE id=? AND deleted_at IS NULL",
        (transaction_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Transaction not found")
    current = row_to_dict(row)
    day = body.day[:10] if body.day else current["day"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day[:10]):
        raise HTTPException(400, "day must be YYYY-MM-DD")
    now = utcnow()
    await db.execute(
        """
        UPDATE finance_transactions SET
          category_id=?, account_id=?, kind=?, amount=?, day=?, note=?, updated_at=?
        WHERE id=?
        """,
        (
            body.category_id if body.category_id is not None else current["category_id"],
            body.account_id if body.account_id is not None else current["account_id"],
            body.kind if body.kind is not None else current["kind"],
            body.amount if body.amount is not None else current["amount"],
            day[:10],
            body.note if body.note is not None else current["note"],
            now,
            transaction_id,
        ),
    )
    await log_action(db, "updated", "finance_transaction", transaction_id, {})
    await db.commit()
    cur = await db.execute("SELECT * FROM finance_transactions WHERE id=?", (transaction_id,))
    return row_to_dict(await cur.fetchone())


@router.delete("/transactions/{transaction_id}")
async def delete_finance_transaction(
    transaction_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    now = utcnow()
    cur = await db.execute(
        "UPDATE finance_transactions SET deleted_at=?, updated_at=? WHERE id=? AND deleted_at IS NULL",
        (now, now, transaction_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Transaction not found")
    await log_action(db, "deleted", "finance_transaction", transaction_id, {})
    await db.commit()
    return {"ok": True}


@router.put("/budget/{year_month}/{category_id}")
async def upsert_finance_budget(
    year_month: str,
    category_id: int,
    body: FinanceBudgetIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    _validate_year_month(year_month)
    cur = await db.execute(
        "SELECT id FROM finance_categories WHERE id=? AND deleted_at IS NULL",
        (category_id,),
    )
    if not await cur.fetchone():
        raise HTTPException(404, "Category not found")
    await db.execute(
        """
        INSERT INTO finance_budget(year_month, category_id, planned)
        VALUES(?,?,?)
        ON CONFLICT(year_month, category_id) DO UPDATE SET planned=excluded.planned
        """,
        (year_month, category_id, body.planned),
    )
    await log_action(
        db,
        "updated",
        "finance_budget",
        category_id,
        {"year_month": year_month, "planned": body.planned},
    )
    await db.commit()
    return {"year_month": year_month, "category_id": category_id, "planned": body.planned}


def _parse_amount(raw: str) -> float | None:
    s = (raw or "").strip().replace("\u00a0", " ").replace(" ", "")
    s = s.replace("₽", "").replace("р.", "").replace("руб", "").replace(",", ".")
    if not s:
        return None
    try:
        return abs(float(s))
    except ValueError:
        return None


@router.post("/import-csv")
async def import_finance_csv(
    body: FinanceImportIn,
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    """Import rows from exported CSV. Sheet must be shared or user pastes export."""
    await ensure_finance_sheet_defaults(db)
    reader = csv.reader(io.StringIO(body.csv_text))
    rows = list(reader)
    if len(rows) < 2:
        raise HTTPException(400, "CSV too short")
    header = [h.strip().lower() for h in rows[0]]
    imported = {"transactions": 0, "budget": 0, "skipped": 0}

    def col(*names: str) -> int | None:
        for n in names:
            for i, h in enumerate(header):
                if n in h:
                    return i
        return None

    idx_cat = col("категор", "category", "статья")
    idx_sum = col("сумм", "amount", "факт", "расход", "доход")
    idx_day = col("дата", "date")
    idx_note = col("коммент", "note", "опис")
    idx_plan = col("план", "budget", "plan")
    idx_kind = col("тип", "type", "вид")

    cur = await db.execute(
        "SELECT id, name, kind FROM finance_categories WHERE deleted_at IS NULL"
    )
    cat_by_name = {(r["name"].lower(), r["kind"]): r["id"] for r in await cur.fetchall()}
    now = utcnow()
    default_ym = body.year_month or utcnow()[:7]

    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            imported["skipped"] += 1
            continue
        cat_name = row[idx_cat].strip() if idx_cat is not None and idx_cat < len(row) else ""
        amount = _parse_amount(row[idx_sum]) if idx_sum is not None and idx_sum < len(row) else None
        if amount is None:
            imported["skipped"] += 1
            continue
        kind_raw = row[idx_kind].strip().lower() if idx_kind is not None and idx_kind < len(row) else ""
        kind = "income" if any(x in kind_raw for x in ("доход", "income", "+")) else "expense"
        cat_key = (cat_name.lower(), kind)
        category_id = cat_by_name.get(cat_key)
        if cat_name and not category_id:
            cur = await db.execute(
                """
                INSERT INTO finance_categories(name, kind, group_name, sort, created_at, updated_at)
                VALUES(?,?,?,?,?,?)
                """,
                (cat_name, kind, "Импорт", 900, now, now),
            )
            category_id = cur.lastrowid
            cat_by_name[cat_key] = category_id

        day = today = utcnow()[:10]
        if idx_day is not None and idx_day < len(row) and row[idx_day].strip():
            day = row[idx_day].strip()[:10]
        note = row[idx_note].strip() if idx_note is not None and idx_note < len(row) else ""

        await db.execute(
            """
            INSERT INTO finance_transactions(
              category_id, account_id, kind, amount, day, note, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (category_id, None, kind, amount, day, note, now, now),
        )
        imported["transactions"] += 1

        if idx_plan is not None and idx_plan < len(row) and category_id:
            planned = _parse_amount(row[idx_plan])
            if planned is not None:
                ym = default_ym
                if len(day) >= 7:
                    ym = day[:7]
                await db.execute(
                    """
                    INSERT INTO finance_budget(year_month, category_id, planned)
                    VALUES(?,?,?)
                    ON CONFLICT(year_month, category_id) DO UPDATE SET planned=excluded.planned
                    """,
                    (ym, category_id, planned),
                )
                imported["budget"] += 1

    await log_action(db, "imported", "finance_csv", None, imported)
    await db.commit()
    return {"ok": True, **imported}


def register_finance_sheet(app) -> None:
    app.include_router(router)
