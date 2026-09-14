# Finance Excel sheet synced to tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finance page is an Excel-like budget grid whose Fact column is the sum of categorized tasks, manual transactions, and work payments for that month.

**Architecture:** Extract category resolve + month key into `app/finance_task_sync.py`. Tasks get `finance_category_id`; create/patch auto-maps by `projects.name` + `cost_type` (income and expense = two rows). `GET /api/finance/sheet` stops dumping all tasks into «Прочие *»; it sums by category and attaches `fact_entries`. UI drops the txn form/journal; Fact click opens a drawer; cells use Tab/Enter/arrows.

**Tech Stack:** FastAPI, aiosqlite, unittest, vanilla `static/app.js` + `static/styles.css`.

**Spec:** `docs/superpowers/specs/2026-09-14-finance-excel-task-sync-design.md`

## Global Constraints

- No formulas, extra columns, copy-paste, or fill-handle.
- Task month = `due_at`; if missing, `created_at`. Do **not** use `completed_at` for the month bucket (this replaces today's `COALESCE(completed_at, due_at, created_at)`).
- Income and expense of the same project name are two categories, same `name`, different `kind`.
- Work payments land on category **Работа** / `kind=income` (create if missing). Not «Подработка».
- Delete category with any live task / txn / work-on-that-row → HTTP 409.
- Duplicate live `(name, kind)` → HTTP 409.
- Goals section is out of scope.
- Do not invent new money on live DB during browser verify.
- Cache bump: `static/index.html` `app.js?v=77`, `styles.css?v=50`, `static/sw.js` `notetask-v29`, `static/pwa.js` `sw.js?v=29`.
- Commit messages: conventional English, subject ≤72 chars.

## File map

- Create: `app/finance_task_sync.py` — month key, resolve/create category, backfill.
- Create: `tests/test_finance_task_sync.py`
- Create: `tests/test_finance_sheet_fact.py`
- Modify: `app/db.py` — `ensure_column(tasks, finance_category_id)`.
- Modify: `app/main.py` — `TaskIn` / `TaskPatchIn`, INSERT/UPDATE on create/patch/put.
- Modify: `app/finance_sheet.py` — sheet actuals + `fact_entries`, delete/create category 409, drop `_rollup_task_work_budget` task lumping.
- Modify: `static/app.js` — grid, drawer, keyboard, create-task-from-row; remove `#fin-tx-form` and page journal.
- Modify: `static/styles.css` — selected cell, drawer, `+` column.
- Modify: `static/index.html`, `static/sw.js`, `static/pwa.js` — cache (`sw.js?v=29`).

---

### Task 1: Category resolve + month key

**Files:**
- Create: `app/finance_task_sync.py`
- Test: `tests/test_finance_task_sync.py`

**Interfaces:**
- Consumes: `aiosqlite.Connection`; tables `projects`, `finance_categories` (same columns as `app/db.py` / `finance_sheet.py`).
- Produces:
  - `UNCATEGORIZED_NAME = "Без раздела"`
  - `WORK_CATEGORY_NAME = "Работа"`
  - `def task_month_key(due_at: str | None, created_at: str | None) -> str | None`
  - `async def get_or_create_category(db, *, name: str, kind: str) -> int`
  - `async def resolve_finance_category_id(db, *, project_id: int | None, cost_type: str | None, finance_category_id: int | None = None, has_cost: bool) -> int | None`
  - `async def backfill_task_categories(db) -> int`

- [ ] **Step 1: Write the failing tests**

```python
import unittest

import aiosqlite

from app.finance_task_sync import (
    UNCATEGORIZED_NAME,
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
```

- [ ] **Step 2: Run tests, expect fail**

Run: `python -m unittest tests.test_finance_task_sync -v`

Expected: `ModuleNotFoundError: app.finance_task_sync`

- [ ] **Step 3: Implement `app/finance_task_sync.py`**

```python
from __future__ import annotations

from typing import Any

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
```

- [ ] **Step 4: Re-run tests**

Run: `python -m unittest tests.test_finance_task_sync -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/finance_task_sync.py tests/test_finance_task_sync.py
git commit -m "feat(finance): resolve category from project name"
```

---

### Task 2: Column + task create/patch/put

**Files:**
- Modify: `app/db.py` — after the `remind_rule` `ensure_column` (~line 206), add `finance_category_id`.
- Modify: `app/main.py` — `TaskIn` / `TaskPatchIn`; `create_task` INSERT; `patch_task` and `update_task` UPDATE lists.
- Test: `tests/test_finance_task_sync.py` — add `BackfillTests`.

**Interfaces:**
- Consumes: `resolve_finance_category_id(db, project_id=..., cost_type=..., finance_category_id=..., has_cost=...)`
- Produces: task rows include `finance_category_id`. PATCH: if `finance_category_id` in body (including null) use resolve with that value; if omitted and `project_id` changed, rematch; if omitted and project unchanged, keep old id.

- [ ] **Step 1: Write failing backfill test** (same file, new class)

```python
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
        from app.finance_task_sync import WORK_CATEGORY_NAME, backfill_task_categories

        n = await backfill_task_categories(self.db)
        self.assertEqual(n, 1)
        cur = await self.db.execute("SELECT finance_category_id FROM tasks WHERE id=1")
        cid = (await cur.fetchone())["finance_category_id"]
        cur = await self.db.execute("SELECT name, kind FROM finance_categories WHERE id=?", (cid,))
        row = await cur.fetchone()
        self.assertEqual(row["name"], WORK_CATEGORY_NAME)
        self.assertEqual(row["kind"], "income")
```

- [ ] **Step 2: Run `python -m unittest tests.test_finance_task_sync.BackfillTests -v`**

Expected: PASS if Task 1 already has `backfill_task_categories`; if you skipped it, implement now.

- [ ] **Step 3: Add column in `app/db.py` `migrate`**

After `ensure_column(db, "tasks", "remind_rule", "TEXT")`:

```python
    await ensure_column(db, "tasks", "finance_category_id", "INTEGER")
```

- [ ] **Step 4: Wire `app/main.py`**

Add to `TaskIn` and `TaskPatchIn`:

```python
    finance_category_id: int | None = None
```

In `create_task`, after `work_project_id = await normalize_work_project_id(...)`:

```python
    from .finance_task_sync import resolve_finance_category_id

    finance_category_id = await resolve_finance_category_id(
        db,
        project_id=body.project_id,
        cost_type=body.cost_type,
        finance_category_id=body.finance_category_id,
        has_cost=body.cost is not None and float(body.cost) != 0,
    )
```

Add `finance_category_id` to the INSERT column list and values.

In `patch_task`, after remind prepare, before UPDATE:

```python
    from .finance_task_sync import resolve_finance_category_id

    has_cost = next_values.get("cost") is not None and float(next_values.get("cost") or 0) != 0
    if "finance_category_id" in patch:
        next_values["finance_category_id"] = await resolve_finance_category_id(
            db,
            project_id=next_values.get("project_id"),
            cost_type=next_values.get("cost_type"),
            finance_category_id=patch.get("finance_category_id"),
            has_cost=has_cost,
        )
    elif "project_id" in patch and has_cost:
        next_values["finance_category_id"] = await resolve_finance_category_id(
            db,
            project_id=next_values.get("project_id"),
            cost_type=next_values.get("cost_type"),
            has_cost=True,
        )
```

Add `finance_category_id=?` to both UPDATE statements (patch + put). For `update_task` (full PUT), always resolve with `body.finance_category_id`.

- [ ] **Step 5: Run**

`python -m unittest tests.test_finance_task_sync tests.test_due_window tests.test_finance_income -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db.py app/main.py tests/test_finance_task_sync.py
git commit -m "feat(tasks): store finance_category_id"
```

---

### Task 3: Sheet Fact by category + 409s

**Files:**
- Modify: `app/finance_sheet.py`
- Test: `tests/test_finance_sheet_fact.py`

**Interfaces:**
- Consumes: `task_month_key`, `get_or_create_category`, `backfill_task_categories`, `WORK_CATEGORY_NAME`
- Produces: each `categories[]` item has `planned`, `actual`, `delta`, `fact_entries` where entry is `{source: "task"|"sheet"|"work", id, title, amount, day, task_id}`. Work payments only on Работа/income. Month filter for tasks uses `task_month_key` (due then created). Remove `_rollup_task_work_budget` usage for tasks/work (keep function deleted).

- [ ] **Step 1: Write failing sheet tests**

Build an in-memory schema with `projects`, `finance_categories`, `finance_transactions`, `finance_budget`, `finance_accounts`, `finance_months`, `tasks`, `work_projects`, `work_project_payments`. Seed defaults via `ensure_finance_sheet_defaults`. Insert:

- project Здоровье
- task expense 1000 due `2026-08-10` in Здоровье
- task income 2000 due `2026-08-10` in Здоровье
- txn expense 100 on ЖКХ day `2026-08-05`
- work payment received 250000 paid `2026-08-20`

Call `get_finance_sheet` with a fake auth bypass: extract a pure function instead if Depends is painful.

Prefer testing helpers you add next to the router:

```python
async def category_actuals_for_month(db, year_month: str) -> dict[int, list[dict]]
```

Then `get_finance_sheet` uses that. Tests call `category_actuals_for_month` + `backfill_task_categories` + `ensure_finance_sheet_defaults`.

Assertions:

1. Здоровье/expense `actual == 1000`, one `fact_entries` source=task.
2. Здоровье/income `actual == 2000`, separate category id.
3. ЖКХ `actual == 100`, source=sheet.
4. Работа/income `actual == 250000`, source=work.
5. «Прочие расходы» / «Подработка» actuals do **not** include those task/work sums.

Also:

```python
async def test_delete_category_with_task_409(...)
async def test_create_duplicate_name_kind_409(...)
```

These can use `TestClient` if you already have `app` + temp DB; otherwise call `delete_finance_category` / `create_finance_category` with a stub user. Simpler: add `category_has_entries(db, category_id) -> bool` and `assert_unique_live_category(db, name, kind, exclude_id=None)` and unit-test those; wire HTTP 409 in the endpoints.

```python
async def test_occupied_category_has_entries(self):
    ...
    self.assertTrue(await category_has_entries(self.db, zdrav_expense_id))
    self.assertFalse(await category_has_entries(self.db, empty_id))
```

- [ ] **Step 2: Run `python -m unittest tests.test_finance_sheet_fact -v`**

Expected: FAIL import or missing functions.

- [ ] **Step 3: Implement in `app/finance_sheet.py`**

Add:

```python
from .finance_task_sync import (
    WORK_CATEGORY_NAME,
    backfill_task_categories,
    get_or_create_category,
    task_month_key,
)

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
```
```

`get_finance_sheet` after defaults:

```python
    await backfill_task_categories(db)
    work_cat_id = await get_or_create_category(db, name=WORK_CATEGORY_NAME, kind="income")
```

Replace task day SQL with due/created only. Group task sums by `finance_category_id`. Attach `fact_entries` per category. Add work entries only to `work_cat_id`. Delete `_rollup_task_work_budget` and its call.

`create_finance_category`: before INSERT, if live `(name, kind)` exists → `HTTPException(409, "Category already exists")`.

`delete_finance_category`: if `await category_has_entries(...)` → `HTTPException(409, "Category has entries")`.

- [ ] **Step 4: Run**

`python -m unittest tests.test_finance_sheet_fact tests.test_finance_income tests.test_finance_task_sync -v`

Expected: PASS. Old income helper still 250k in August.

- [ ] **Step 5: Commit**

```bash
git add app/finance_sheet.py tests/test_finance_sheet_fact.py
git commit -m "feat(finance): Fact by category plus task entries"
```

---

### Task 4: Excel grid UI + Fact drawer

**Files:**
- Modify: `static/app.js` — `renderFinancePage` (~1913–2108), click/change/submit listeners (~4049–4108)
- Modify: `static/styles.css` — after `.fin-budget-table` (~2002)

**Interfaces:**
- Consumes: `GET /api/finance/sheet` with `categories[].fact_entries`, `planned`, `actual`, `delta`
- Produces: no `#fin-tx-form`; no page-level `.fin-ops-page` journal. Drawer `#fin-fact-drawer` lists `fact_entries`. `POST /api/tasks` from row `+`.

- [ ] **Step 1: CSS**

Add after existing `.fin-budget-table` rules:

```css
.fin-budget-table col.col-plus { width: 44px; }
.fin-budget-table tr.is-selected td { outline: 2px solid var(--accent, #2f6f4e); outline-offset: -2px; }
.fin-budget-table td.cat-name[contenteditable="true"],
.fin-budget-table .fin-plan-input {
  width: 100%;
  border: 0;
  background: transparent;
  font: inherit;
}
.fin-budget-table td.is-fact { cursor: pointer; text-decoration: underline dotted; }
.fin-row-add { margin: 8px 0 16px; }
.fin-drawer {
  position: fixed;
  right: 0; top: 0; bottom: 0;
  width: min(420px, 100vw);
  background: var(--panel, #fff);
  border-left: 1px solid var(--line, #ddd);
  z-index: 40;
  padding: 16px;
  overflow: auto;
}
.fin-drawer.hidden { display: none; }
@media (max-width: 860px) {
  .fin-budget-sheet { overflow-x: auto; }
  .fin-budget-table { min-width: 640px; }
}
```

- [ ] **Step 2: Rewrite `renderFinancePage` budget + drop form/journal**

Keep hero (month, balance, split, accounts). For each group, table columns: Статья | План | Факт | Δ | +.

Name cell: `td.cat-name` with `contenteditable="true"` `data-fin-name="{id}"` `data-fin-kind="{kind}"`.

Plan: existing `input.fin-plan-input`.

Fact: `td.is-fact` `data-fin-fact="{id}"` — not an input.

Plus: `<button type="button" class="btn ghost small" data-fin-new-task="{id}" data-fin-kind="{kind}">+</button>`

After each group: `<button type="button" class="btn ghost small fin-row-add" data-fin-add-row data-fin-kind="{firstCat.kind}" data-fin-group="{groupName}">+ строка</button>`

After tables, add once:

```html
<div id="fin-fact-drawer" class="fin-drawer hidden" hidden></div>
```

Remove `#fin-tx-form` and the «Операции» section.

- [ ] **Step 3: Events on `#finance-page`**

Replace submit handler for `#fin-tx-form` with no-op (form gone).

Click:

- `[data-fin-fact]` → render drawer from `state.financeSheet.categories` find id → `fact_entries`. Button «+ задача» calls same create helper.
- `[data-finance-task]` / `[data-fin-open-task]` → `setView("today")`, then existing pulse/scroll: `document.querySelector(\`.item[data-id="${taskId}"]\`)` + `anim-pulse` + `scrollIntoView` (same as `#section-panel` handler ~3844). NoteTask has no task modal.
- `[data-fin-new-task]` → `prompt` title + amount (or a tiny inline form in the drawer). `POST /api/tasks` `{ title, cost, cost_type: kind, finance_category_id, project_id }` where `project_id` = project whose name equals category.name (search `state.projects`), else null. Then `loadFinancePage()`.
- `[data-fin-add-row]` → `POST /api/finance/categories` `{ name: "Новая статья", kind, group_name }` then reload.
- Delete: selected row + Delete key, or button on selected row → `DELETE /api/finance/categories/{id}`; on 409 show the server detail.

Change:

- plan input: keep current PUT budget.
- blur on `[data-fin-name]`: `PATCH /api/finance/categories/{id}` with `{ name, kind, group_name, sort }` from the category object.

Keyboard on `#finance-page` (delegate `keydown`):

- Ignore when target is drawer inputs except arrows between name/plan cells.
- Arrow keys move `.is-selected` among `tr[data-fin-cat]`.
- Tab / Shift+Tab cycle name ↔ plan in the selected row, then next row.
- Enter on plan/name: next row same column.
- Escape: close drawer / blur.
- Delete/Backspace when selected row and focus not in an input: try delete category.

Keep `state.financeSheet = data` in `renderFinancePage`.

- [ ] **Step 4: Manual UI check is Task 5. Commit UI.**

```bash
git add static/app.js static/styles.css
git commit -m "feat(finance): Excel grid and Fact drawer"
```

---

### Task 5: Cache bump + browser verify

**Files:**
- Modify: `static/index.html` — `styles.css?v=50`, `app.js?v=77`
- Modify: `static/sw.js` — `CACHE = "notetask-v29"`
- Modify: `static/pwa.js` — `sw.js?v=29`

- [ ] **Step 1: Bump versions** as above. If `static/pwa.js` lists asset query strings, bump those too.

- [ ] **Step 2: Restart backend if needed** (`docker restart notetask` or the local process that serves `:8100`).

- [ ] **Step 3: Browser** on `http://192.168.0.6/` or `https://todo.baski.pro/`

Verify, **do not enter new sums**:

1. Финансы opens; hero + grid; no «Добавить» txn form; no bottom journal.
2. Existing task amounts sit on rows named like their section; income/expense split.
3. Click Fact → drawer lists those tasks/записи/работа.
4. Tab / Enter moves between name and plan.
5. «+» opens create (cancel without save).
6. Work received still in **Работа** income, not Подработка.

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/sw.js static/pwa.js
git commit -m "chore(web): bump finance sheet cache"
```

---

## Spec coverage

| Spec | Task |
|---|---|
| `tasks.finance_category_id` | 2 |
| Auto-map project name + kind split | 1, 2 |
| Fact = tasks + manual + work | 3 |
| Month = due / created | 1, 3 |
| Work → Работа income | 3 |
| Excel cells / keys / add-delete row | 4 |
| Hero stays, journal = Fact click | 4 |
| Create task from row | 4 |
| 409 delete/duplicate | 3 |
| Backfill | 1, 3 |
| Browser, no new money | 5 |
| No formulas / no Goals | (out of plan) |
