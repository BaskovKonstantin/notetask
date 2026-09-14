import sys
import types
import unittest


def _install_import_stubs() -> None:
    """Host venv is Python 3.14; pydantic/fastapi wheels do not build here."""
    if "fastapi" in sys.modules:
        return

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: object = None, headers: object = None) -> None:
            super().__init__(str(detail))
            self.status_code = status_code
            self.detail = detail
            self.headers = headers

    class _Router:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _deco(self, *args: object, **kwargs: object):
            def wrap(fn):
                return fn

            return wrap

        get = post = patch = delete = put = _deco

    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = _Router
    fastapi.Depends = lambda *a, **k: None
    fastapi.HTTPException = HTTPException
    fastapi.status = types.SimpleNamespace(HTTP_401_UNAUTHORIZED=401)
    sys.modules["fastapi"] = fastapi

    security = types.ModuleType("fastapi.security")

    class HTTPBearer:
        def __init__(self, auto_error: bool = False) -> None:
            pass

    class HTTPAuthorizationCredentials:
        pass

    security.HTTPBearer = HTTPBearer
    security.HTTPAuthorizationCredentials = HTTPAuthorizationCredentials
    sys.modules["fastapi.security"] = security
    fastapi.security = security

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        pass

    def Field(*args: object, **kwargs: object) -> None:
        return None

    pydantic.BaseModel = BaseModel
    pydantic.Field = Field
    sys.modules["pydantic"] = pydantic

    jwt_mod = types.ModuleType("jwt")
    jwt_mod.encode = lambda *a, **k: ""
    jwt_mod.decode = lambda *a, **k: {}
    jwt_mod.PyJWTError = type("PyJWTError", (Exception,), {})
    sys.modules["jwt"] = jwt_mod


_install_import_stubs()

import aiosqlite
from fastapi import HTTPException

from app.finance_sheet import (
    assert_unique_live_category,
    category_actuals_for_month,
    category_has_entries,
    ensure_finance_sheet_defaults,
)
from app.finance_task_sync import backfill_task_categories


class SheetFactByCategoryTests(unittest.IsolatedAsyncioTestCase):
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
            CREATE TABLE finance_accounts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              sort INTEGER NOT NULL DEFAULT 0,
              opening_balance REAL NOT NULL DEFAULT 0,
              deleted_at TEXT,
              created_at TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE finance_transactions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              category_id INTEGER,
              account_id INTEGER,
              kind TEXT NOT NULL DEFAULT 'expense',
              amount REAL NOT NULL,
              day TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '',
              deleted_at TEXT,
              created_at TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE finance_budget (
              year_month TEXT NOT NULL,
              category_id INTEGER NOT NULL,
              planned REAL NOT NULL DEFAULT 0,
              PRIMARY KEY (year_month, category_id)
            );
            CREATE TABLE finance_months (
              year_month TEXT PRIMARY KEY,
              income REAL NOT NULL DEFAULT 0,
              expense REAL NOT NULL DEFAULT 0,
              notes TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id INTEGER,
              title TEXT NOT NULL DEFAULT '',
              cost REAL,
              cost_type TEXT,
              finance_category_id INTEGER,
              due_at TEXT,
              created_at TEXT,
              completed_at TEXT,
              deleted_at TEXT
            );
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
            INSERT INTO projects(id, name) VALUES (1, 'Здоровье');
            """
        )
        await self.db.commit()
        await ensure_finance_sheet_defaults(self.db)

        zhkh_id = await self._cat_id("ЖКХ", "expense")
        await self.db.execute(
            """
            INSERT INTO tasks(project_id, title, cost, cost_type, due_at, created_at)
            VALUES (1, 'Врач', 1000, 'expense', '2026-08-10', '2026-08-01T00:00:00')
            """
        )
        await self.db.execute(
            """
            INSERT INTO tasks(project_id, title, cost, cost_type, due_at, created_at)
            VALUES (1, 'Возврат', 2000, 'income', '2026-08-10', '2026-08-01T00:00:00')
            """
        )
        await self.db.execute(
            """
            INSERT INTO finance_transactions(
              category_id, kind, amount, day, note, created_at, updated_at
            ) VALUES (?, 'expense', 100, '2026-08-05', 'квартплата', '', '')
            """,
            (zhkh_id,),
        )
        await self.db.execute(
            "INSERT INTO work_projects(id, title) VALUES (1, 'Снеговики')"
        )
        await self.db.execute(
            """
            INSERT INTO work_project_payments(
              work_project_id, amount, paid_at, status, created_at
            ) VALUES (1, 250000, '2026-08-20', 'received', '2026-08-20T00:00:00+00:00')
            """
        )
        await self.db.commit()
        await backfill_task_categories(self.db)
        self.actuals = await category_actuals_for_month(self.db, "2026-08")

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def _cat_id(self, name: str, kind: str) -> int:
        cur = await self.db.execute(
            """
            SELECT id FROM finance_categories
            WHERE deleted_at IS NULL AND name=? AND kind=?
            """,
            (name, kind),
        )
        row = await cur.fetchone()
        self.assertIsNotNone(row, f"missing category {name}/{kind}")
        return int(row["id"])

    def _sum(self, category_id: int) -> float:
        return sum(float(e["amount"] or 0) for e in self.actuals.get(category_id, []))

    async def test_zdorovie_expense_actual_from_task(self) -> None:
        cid = await self._cat_id("Здоровье", "expense")
        entries = self.actuals.get(cid, [])
        self.assertEqual(self._sum(cid), 1000)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "task")
        self.assertEqual(entries[0]["amount"], 1000)
        self.assertEqual(entries[0]["task_id"], entries[0]["id"])

    async def test_zdorovie_income_separate_category(self) -> None:
        exp_id = await self._cat_id("Здоровье", "expense")
        inc_id = await self._cat_id("Здоровье", "income")
        self.assertNotEqual(exp_id, inc_id)
        entries = self.actuals.get(inc_id, [])
        self.assertEqual(self._sum(inc_id), 2000)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "task")

    async def test_zhkh_sheet_actual(self) -> None:
        cid = await self._cat_id("ЖКХ", "expense")
        entries = self.actuals.get(cid, [])
        self.assertEqual(self._sum(cid), 100)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "sheet")

    async def test_work_income_on_rabota(self) -> None:
        cid = await self._cat_id("Работа", "income")
        entries = self.actuals.get(cid, [])
        self.assertEqual(self._sum(cid), 250000)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "work")

    async def test_misc_rows_do_not_absorb_task_or_work(self) -> None:
        other_exp = await self._cat_id("Прочие расходы", "expense")
        sidework = await self._cat_id("Подработка", "income")
        self.assertEqual(self._sum(other_exp), 0)
        self.assertEqual(self._sum(sidework), 0)
        self.assertEqual(self.actuals.get(other_exp, []), [])
        self.assertEqual(self.actuals.get(sidework, []), [])

    async def test_occupied_category_has_entries(self) -> None:
        zdrav_expense_id = await self._cat_id("Здоровье", "expense")
        empty_id = await self._cat_id("Образование", "expense")
        self.assertTrue(await category_has_entries(self.db, zdrav_expense_id))
        self.assertFalse(await category_has_entries(self.db, empty_id))

    async def test_delete_category_with_task_409(self) -> None:
        zdrav = await self._cat_id("Здоровье", "expense")
        self.assertTrue(await category_has_entries(self.db, zdrav))

    async def test_create_duplicate_name_kind_409(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await assert_unique_live_category(self.db, "ЖКХ", "expense")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "Category already exists")

    async def test_patch_rename_duplicate_name_kind_409(self) -> None:
        education_id = await self._cat_id("Образование", "expense")
        with self.assertRaises(HTTPException) as ctx:
            await assert_unique_live_category(
                self.db, "ЖКХ", "expense", exclude_id=education_id
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "Category already exists")


if __name__ == "__main__":
    unittest.main()
