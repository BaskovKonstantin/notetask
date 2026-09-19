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

from app.finance_helpers import reassign_work_payment_project
from app.finance_ledger import WORK_SECTION_NAME, list_finance_ledger_rows
from app.finance_task_sync import UNCATEGORIZED_NAME


SCHEMA = """
CREATE TABLE projects (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER,
  title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'task',
  status TEXT NOT NULL DEFAULT 'open',
  due_at TEXT,
  deleted_at TEXT,
  cost REAL,
  cost_type TEXT,
  created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE work_projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
  created_at TEXT NOT NULL DEFAULT ''
);
"""


class LedgerRowsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.execute("INSERT INTO projects(id, name) VALUES (1, 'Личные дела'), (2, 'Работа')")
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_task_income_expense_and_work(self) -> None:
        await self.db.execute(
            """
            INSERT INTO tasks(id, project_id, title, status, due_at, cost, cost_type)
            VALUES
              (1, 1, 'Cursor', 'open', '2026-09-30', 20000, 'expense'),
              (2, 2, 'CRM', 'done', '2026-08-31', 255000, 'income')
            """
        )
        await self.db.execute("INSERT INTO work_projects(id, title) VALUES (9, 'Снеговики')")
        await self.db.execute(
            """
            INSERT INTO work_project_payments(id, work_project_id, amount, paid_at, status)
            VALUES (3, 9, 250000, '2026-09-30', 'planned')
            """
        )
        await self.db.commit()
        rows = await list_finance_ledger_rows(self.db)
        by_key = {(r["source"], r["id"]): r for r in rows}
        self.assertEqual(by_key[("task", 1)]["amount"], -20000)
        self.assertEqual(by_key[("task", 1)]["status"], "plan")
        self.assertEqual(by_key[("task", 1)]["project_name"], "Личные дела")
        self.assertEqual(by_key[("task", 1)]["day"], "2026-09-30")
        self.assertEqual(by_key[("task", 2)]["amount"], 255000)
        self.assertEqual(by_key[("task", 2)]["status"], "confirmed")
        self.assertEqual(by_key[("work", 3)]["amount"], 250000)
        self.assertEqual(by_key[("work", 3)]["status"], "plan")
        self.assertEqual(by_key[("work", 3)]["title"], "Снеговики")
        self.assertEqual(by_key[("work", 3)]["project_name"], WORK_SECTION_NAME)
        self.assertEqual(by_key[("work", 3)]["work_project_id"], 9)
        self.assertEqual(by_key[("work", 3)]["project_id"], 2)

    async def test_zero_cost_and_deleted_excluded(self) -> None:
        await self.db.execute(
            """
            INSERT INTO tasks(id, project_id, title, cost, cost_type, deleted_at)
            VALUES
              (1, 1, 'Zero', 0, 'expense', NULL),
              (2, 1, 'Gone', 100, 'expense', '2026-09-01')
            """
        )
        await self.db.commit()
        rows = await list_finance_ledger_rows(self.db)
        self.assertEqual(rows, [])

    async def test_no_due_still_listed(self) -> None:
        await self.db.execute(
            "INSERT INTO tasks(id, project_id, title, cost, cost_type, due_at) VALUES (1, 1, 'Еда', 20, 'expense', NULL)"
        )
        await self.db.commit()
        rows = await list_finance_ledger_rows(self.db)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["day"])
        self.assertEqual(rows[0]["project_name"], "Личные дела")

    async def test_no_project_uses_uncategorized(self) -> None:
        await self.db.execute(
            "INSERT INTO tasks(id, project_id, title, cost, cost_type, due_at) VALUES (1, NULL, 'X', 5, 'expense', '2026-10-01')"
        )
        await self.db.commit()
        rows = await list_finance_ledger_rows(self.db)
        self.assertEqual(rows[0]["project_name"], UNCATEGORIZED_NAME)
        self.assertIsNone(rows[0]["project_id"])

    async def test_sort_day_desc_nulls_last(self) -> None:
        await self.db.execute(
            """
            INSERT INTO tasks(id, project_id, title, cost, cost_type, due_at)
            VALUES
              (1, 1, 'A', 1, 'expense', '2026-08-01'),
              (2, 1, 'B', 1, 'expense', NULL),
              (3, 1, 'C', 1, 'expense', '2026-10-01')
            """
        )
        await self.db.commit()
        ids = [r["id"] for r in await list_finance_ledger_rows(self.db)]
        self.assertEqual(ids, [3, 1, 2])

    async def test_deleted_work_project_hides_payments(self) -> None:
        await self.db.execute(
            "INSERT INTO work_projects(id, title, deleted_at) VALUES (1, 'Old', '2026-01-01')"
        )
        await self.db.execute(
            "INSERT INTO work_project_payments(work_project_id, amount, paid_at, status) VALUES (1, 100, '2026-09-01', 'received')"
        )
        await self.db.commit()
        self.assertEqual(await list_finance_ledger_rows(self.db), [])


class WorkPaymentReassignTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_move_to_another_live_project_keeps_row(self) -> None:
        await self.db.execute("INSERT INTO work_projects(id, title) VALUES (1, 'A'), (2, 'B')")
        await self.db.execute(
            """
            INSERT INTO work_project_payments(id, work_project_id, amount, paid_at, note, status)
            VALUES (10, 1, 250000, '2026-09-15', 'keep me', 'planned')
            """
        )
        await self.db.commit()
        ok = await reassign_work_payment_project(
            self.db, payment_id=10, from_work_project_id=1, to_work_project_id=2
        )
        self.assertTrue(ok)
        cur = await self.db.execute("SELECT * FROM work_project_payments")
        rows = [dict(r) for r in await cur.fetchall()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], 10)
        self.assertEqual(row["work_project_id"], 2)
        self.assertEqual(row["amount"], 250000)
        self.assertEqual(row["paid_at"], "2026-09-15")
        self.assertEqual(row["note"], "keep me")
        self.assertEqual(row["status"], "planned")
