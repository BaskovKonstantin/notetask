import asyncio
import unittest

import aiosqlite

from app.finance_helpers import sum_work_payment_income


class FinanceWorkIncomeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE work_projects (
              id INTEGER PRIMARY KEY,
              title TEXT NOT NULL,
              deleted_at TEXT
            );
            CREATE TABLE work_project_payments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              work_project_id INTEGER NOT NULL,
              amount REAL NOT NULL,
              paid_at TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'received',
              created_at TEXT NOT NULL
            );
            INSERT INTO work_projects(id, title) VALUES (1, 'Demo');
            INSERT INTO work_project_payments(work_project_id, amount, paid_at, status, created_at)
              VALUES (1, 250000, '2026-08-20', 'received', '2026-08-20T00:00:00+00:00');
            INSERT INTO work_project_payments(work_project_id, amount, paid_at, status, created_at)
              VALUES (1, 290000, '2026-09-21', 'planned', '2026-09-01T00:00:00+00:00');
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_sum_received_by_paid_at_month(self) -> None:
        aug = await sum_work_payment_income(self.db, year_month="2026-08")
        sep = await sum_work_payment_income(self.db, year_month="2026-09")
        self.assertEqual(aug, 250000.0)
        self.assertEqual(sep, 0.0)

    async def test_planned_excluded(self) -> None:
        total = await sum_work_payment_income(self.db, year_month="2026-09")
        self.assertEqual(total, 0.0)


if __name__ == "__main__":
    unittest.main()
