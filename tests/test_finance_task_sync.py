import unittest

import aiosqlite

from app.finance_task_sync import (
    UNCATEGORIZED_NAME,
    WORK_CATEGORY_NAME,
    backfill_task_categories,
    get_or_create_category,
    resolve_finance_category_id,
    task_month_key,
)


class TaskMonthKeyTests(unittest.TestCase):
    def test_prefers_due(self) -> None:
        self.assertEqual(task_month_key("2026-08-15", "2026-09-01T00:00:00"), "2026-08")

    def test_falls_back_created(self) -> None:
        self.assertEqual(task_month_key(None, "2026-09-03T12:00:00+00:00"), "2026-09")

    def test_empty(self) -> None:
        self.assertIsNone(task_month_key(None, None))


class ResolveCategoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE projects (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              deleted_at TEXT
            );
            CREATE TABLE finance_categories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              kind TEXT NOT NULL,
              group_name TEXT NOT NULL DEFAULT '',
              sort INTEGER NOT NULL DEFAULT 0,
              deleted_at TEXT,
              created_at TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO projects(id, name) VALUES (1, 'Здоровье');
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_explicit_id_wins(self) -> None:
        cid = await get_or_create_category(self.db, name="ЖКХ", kind="expense")
        got = await resolve_finance_category_id(
            self.db,
            project_id=1,
            cost_type="expense",
            finance_category_id=cid,
            has_cost=True,
        )
        self.assertEqual(got, cid)

    async def test_no_cost_returns_none(self) -> None:
        got = await resolve_finance_category_id(
            self.db, project_id=1, cost_type="expense", has_cost=False
        )
        self.assertIsNone(got)

    async def test_split_income_expense_same_name(self) -> None:
        exp = await resolve_finance_category_id(
            self.db, project_id=1, cost_type="expense", has_cost=True
        )
        inc = await resolve_finance_category_id(
            self.db, project_id=1, cost_type="income", has_cost=True
        )
        self.assertNotEqual(exp, inc)
        cur = await self.db.execute("SELECT name, kind FROM finance_categories ORDER BY kind")
        rows = [(r["name"], r["kind"]) for r in await cur.fetchall()]
        self.assertEqual(rows, [("Здоровье", "expense"), ("Здоровье", "income")])

    async def test_no_project_uses_uncategorized(self) -> None:
        cid = await resolve_finance_category_id(
            self.db, project_id=None, cost_type="expense", has_cost=True
        )
        cur = await self.db.execute("SELECT name FROM finance_categories WHERE id=?", (cid,))
        self.assertEqual((await cur.fetchone())["name"], UNCATEGORIZED_NAME)


class BackfillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE projects (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL, deleted_at TEXT
            );
            CREATE TABLE finance_categories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL, kind TEXT NOT NULL,
              group_name TEXT NOT NULL DEFAULT '',
              sort INTEGER NOT NULL DEFAULT 0,
              deleted_at TEXT,
              created_at TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id INTEGER,
              cost REAL,
              cost_type TEXT,
              finance_category_id INTEGER,
              deleted_at TEXT
            );
            INSERT INTO projects(id, name) VALUES (1, 'Работа');
            INSERT INTO tasks(id, project_id, cost, cost_type, finance_category_id)
              VALUES (1, 1, 5000, 'income', NULL);
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_backfill_sets_id(self) -> None:
        n = await backfill_task_categories(self.db)
        self.assertEqual(n, 1)
        cur = await self.db.execute("SELECT finance_category_id FROM tasks WHERE id=1")
        cid = (await cur.fetchone())["finance_category_id"]
        cur = await self.db.execute("SELECT name, kind FROM finance_categories WHERE id=?", (cid,))
        row = await cur.fetchone()
        self.assertEqual(row["name"], WORK_CATEGORY_NAME)
        self.assertEqual(row["kind"], "income")
