# Finance ledger table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finance page is an Excel ledger of money rows (task-with-cost or work payment): Проект · Направление · Цена · Месяц · Статус, with column filters and a hero that sums visible rows.

**Architecture:** New helper `list_finance_ledger_rows` in `app/finance_ledger.py` unions tasks (`cost != 0`) and live work-project payments into signed rows. `GET /api/finance/ledger` returns them. UI drops Статья/План/Факт/Δ; inline cell edits call existing task and work-payment endpoints. New `+` row is a local draft until Цена ≠ 0.

**Tech Stack:** FastAPI, aiosqlite, unittest, vanilla `static/app.js` + `static/styles.css`.

**Spec:** `docs/superpowers/specs/2026-09-15-finance-ledger-table-design.md`

## Global Constraints

- No `finance_ledger` table. No drop of `finance_categories` / `finance_budget` / `finance_transactions`.
- No formulas, copy-paste, fill-handle, or totals footer row.
- Do not invent live money (no `cost=0.01` placeholders). Draft stays client-side until Цена ≠ 0.
- Column Проект = `projects.name` (sidebar section). Sheet labels Спортики/Снеговоики/Жизнь/Кредитка are import mapping only — do not create those as sections.
- Месяц = `due_at` (task) or `paid_at` (work). Empty due stays in the table. Do **not** fall back to `created_at`.
- Status UI: План / Подтверждено. API row field: `plan` | `confirmed`.
- Task confirm = `POST /api/tasks/{id}/complete`. Task plan = `PATCH /api/tasks/{id}` `{ status: "open" }`. Work: `PATCH .../payments/{id}` `{ status: "planned"|"received" }`.
- Work payment amount cannot be negative (`WorkPaymentPatch.amount` has `gt=0`). Clamp/ignore minus; zero = alert, keep old.
- Личные дела fin-panel / `finance_months` unchanged.
- Goals out of scope.
- Cache bump last: `static/index.html` `styles.css?v=51` `app.js?v=78`; `static/sw.js` `notetask-v30`; `static/pwa.js` `sw.js?v=30` and `pwa.js?v=14` in index.
- Host `.venv` is Python 3.14 — copy fastapi/pydantic stubs from `tests/test_finance_sheet_fact.py`.
- Tests: `python -m unittest …` (not pytest).
- Commit messages: conventional English, subject ≤72 chars. If `git commit` fails on missing user.identity, stop and do not run `git config`.

## File map

- Create: `app/finance_ledger.py` — row builder.
- Create: `tests/test_finance_ledger.py`
- Modify: `app/finance_sheet.py` — `GET /ledger`.
- Modify: `static/app.js` — `loadFinancePage` / `renderFinancePage` + events; drop budget grid/drawer handlers.
- Modify: `static/styles.css` — ledger table + column filter popover.
- Modify: `static/index.html`, `static/sw.js`, `static/pwa.js` — cache (Task 4).

---

### Task 1: Ledger rows + GET /api/finance/ledger

**Files:**
- Create: `app/finance_ledger.py`
- Create: `tests/test_finance_ledger.py`
- Modify: `app/finance_sheet.py` — add GET `/ledger` after `get_finance_sheet`.

**Interfaces:**
- Consumes: `aiosqlite.Connection`; tables `tasks`, `projects`, `work_projects`, `work_project_payments`.
- Produces:
  - `UNCATEGORIZED_NAME = "Без раздела"` (string constant; may import from `app.finance_task_sync` instead of duplicating).
  - `WORK_SECTION_NAME = "Работа"`
  - `async def list_finance_ledger_rows(db: aiosqlite.Connection) -> list[dict]`
  - Each dict: `source` (`task`|`work`), `id` (int), `project_id` (int|None), `project_name` (str), `title` (str), `amount` (float, signed), `day` (str|None, `YYYY-MM-DD` or longer prefix sliced to 10), `status` (`plan`|`confirmed`), and for `source=work` also `work_project_id` (int).
  - `GET /api/finance/ledger` → `{ "rows": [...], "work_projects": [{ "id", "title" }] }` live work_projects only (`deleted_at IS NULL`), ordered `title`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_finance_ledger.py`. Copy `_install_import_stubs` verbatim from `tests/test_finance_sheet_fact.py` (lines 6–68), call it, then:

```python
import aiosqlite

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
```

Also add `if __name__ == "__main__": unittest.main()` if other finance tests have it; `test_finance_sheet_fact.py` does not — skip.

- [ ] **Step 2: Run tests, expect fail**

Run: `python -m unittest tests.test_finance_ledger -v`

Expected: `ModuleNotFoundError: app.finance_ledger`

- [ ] **Step 3: Implement `app/finance_ledger.py`**

```python
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
        """
        ,
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
```

- [ ] **Step 4: Add GET `/api/finance/ledger` in `app/finance_sheet.py`**

Imports: `from .finance_ledger import list_finance_ledger_rows`

After `get_finance_sheet`:

```python
@router.get("/ledger")
async def get_finance_ledger(
    db: aiosqlite.Connection = Depends(get_db),
    _: dict = Depends(require_auth),
):
    rows = await list_finance_ledger_rows(db)
    cur = await db.execute(
        """
        SELECT id, title FROM work_projects
        WHERE deleted_at IS NULL
        ORDER BY title COLLATE NOCASE, id
        """
    )
    work_projects = [{"id": int(r["id"]), "title": r["title"]} for r in await cur.fetchall()]
    return {"rows": rows, "work_projects": work_projects}
```

- [ ] **Step 5: Re-run tests**

Run: `python -m unittest tests.test_finance_ledger tests.test_finance_sheet_fact tests.test_finance_task_sync -v`

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/finance_ledger.py app/finance_sheet.py tests/test_finance_ledger.py
git commit -m "feat(finance): ledger rows from tasks and work pay"
```

---

### Task 2: Ledger grid UI (read + filters + hero)

**Files:**
- Modify: `static/app.js` — `loadFinancePage`, `renderFinancePage`; add filter/hero helpers. Leave old budget click handlers until Task 3, but they must not fire (no `[data-fin-cat]`).
- Modify: `static/styles.css` — ledger columns + filter menu.

**Interfaces:**
- Consumes: `GET /api/finance/ledger` (`rows`, `work_projects`); `GET /api/finance/sheet?year_month=` only for `accounts` chips (current calendar month).
- Produces: `state.financeLedger = { rows, work_projects }`; `state.financeLedgerFilters` object of column → `Set` of allowed string keys or `null` meaning all; `state.financeDrafts = []` (Task 3 fills). Table columns Проект | Направление | Цена | Месяц | Статус. No month ‹ ›. No Статья/План/Факт. No `#fin-fact-drawer`.

- [ ] **Step 1: CSS after `.fin-budget-table` rules**

```css
.fin-ledger-sheet { overflow-x: auto; }
.fin-ledger-table { width: 100%; border-collapse: collapse; min-width: 720px; }
.fin-ledger-table th,
.fin-ledger-table td {
  border: 1px solid var(--line, #d5ddd7);
  padding: 6px 8px;
  font: inherit;
}
.fin-ledger-table th {
  background: var(--accent, #2f6f4e);
  color: #fff;
  position: relative;
  white-space: nowrap;
}
.fin-ledger-table th button.fin-col-filter {
  margin-left: 6px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.fin-ledger-table tr.is-selected td {
  outline: 2px solid var(--accent, #2f6f4e);
  outline-offset: -2px;
}
.fin-ledger-table .fin-cell-input,
.fin-ledger-table .fin-cell-select {
  width: 100%;
  border: 0;
  background: transparent;
  font: inherit;
}
.fin-filter-menu {
  position: absolute;
  z-index: 30;
  right: 0;
  top: 100%;
  background: var(--panel, #fff);
  color: var(--text, #222);
  border: 1px solid var(--line, #ddd);
  min-width: 180px;
  max-height: 240px;
  overflow: auto;
  padding: 8px;
  text-align: left;
}
.fin-filter-menu.hidden { display: none; }
.fin-filter-menu label { display: flex; gap: 6px; align-items: center; font-weight: 400; }
@media (max-width: 860px) {
  .fin-ledger-sheet { overflow-x: auto; }
}
```

- [ ] **Step 2: Replace `loadFinancePage` / `renderFinancePage`**

Keep `moneyPlain` / `moneySigned`. Add helpers next to them:

```javascript
function ledgerStatusLabel(status) {
  return status === "confirmed" ? "Подтверждено" : "План";
}

function ledgerDayKey(day) {
  if (!day) return "(пусто)";
  return String(day).slice(0, 10);
}

function ledgerVisibleRows() {
  const rows = [...(state.financeLedger?.rows || []), ...(state.financeDrafts || [])];
  const filters = state.financeLedgerFilters || {};
  return rows.filter((row) => {
    const vals = {
      project: row.project_name || "Без раздела",
      title: row.title || "",
      amount: String(row.amount ?? ""),
      day: ledgerDayKey(row.day),
      status: ledgerStatusLabel(row.status),
    };
    for (const [col, allowed] of Object.entries(filters)) {
      if (!allowed) continue;
      if (!allowed.has(vals[col])) return false;
    }
    return true;
  });
}

function ledgerHeroTotals(rows) {
  let income = 0;
  let expense = 0;
  for (const row of rows) {
    const n = Number(row.amount) || 0;
    if (n > 0) income += n;
    else expense += -n;
  }
  return { income, expense, balance: income - expense };
}
```

`loadFinancePage`:

```javascript
async function loadFinancePage() {
  $("finance-page").innerHTML = `<p class="sp-sub">Загрузка…</p>`;
  try {
    const ym = currentYearMonth();
    const [ledger, sheet] = await Promise.all([
      api("/api/finance/ledger"),
      api(`/api/finance/sheet?year_month=${encodeURIComponent(ym)}`),
    ]);
    state.financeLedger = ledger;
    state.financeSheet = sheet;
    renderFinancePage();
  } catch (err) {
    $("finance-page").innerHTML = `<p class="error">${escapeHtml(err.message || "Ошибка")}</p>`;
  }
}
```

`renderFinancePage` builds:
- Hero label **Баланс** (not «Баланса месяца»), values from `ledgerHeroTotals(ledgerVisibleRows())`. Drop `fin-subhint` task/work/txn lines. Drop month nav.
- Accounts from `state.financeSheet.accounts` (same chip HTML as now).
- One table. Header cells: name + `<button type="button" class="fin-col-filter" data-fin-filter-col="project">▾</button>`.
- Body: visible rows. `tr` attrs: `data-fin-row="${source}:${id}"` drafts `data-fin-row="draft:${localId}"`.
- Cells in Task 2 may be read-only text (Task 3 adds inputs). Show formatted money via `moneyPlain` with minus for negative.
- Under table: `<button type="button" class="btn ghost small fin-row-add" data-fin-add-ledger>+ строка</button>` (no-op until Task 3 is fine, or push a draft immediately if helper exists).
- No drawer, no budget groups.

Filter click: toggle `.fin-filter-menu` inside `th` listing unique values from **all** `state.financeLedger.rows` plus drafts for that column. Checkboxes. Change → set `state.financeLedgerFilters[col] = Set of checked labels` (if all checked, set `null`). Re-render. Click outside closes menus.

- [ ] **Step 3: Manual check later in Task 4. Commit UI shell.**

```bash
git add static/app.js static/styles.css
git commit -m "feat(finance): ledger grid replaces budget sheet"
```

---

### Task 3: Inline edit, draft row, delete, keyboard

**Files:**
- Modify: `static/app.js` — `#finance-page` click/change/focusout/keydown; remove budget-category handlers (`data-fin-cat`, drawer, `data-fin-add-row` category POST, month shift). Keep `openFinanceTask` unused or delete if nothing calls it.

**Interfaces:**
- Consumes: ledger rows; `state.projects`; `state.financeLedger.work_projects`.
- Produces: cell PATCH/POST/DELETE as spec. Draft: `{ source: "draft", id: negative increment, project_id, project_name, title: "Новая строка", amount: 0, day: today ISO date, status: "plan" }`. POST `/api/tasks` when amount ≠ 0.

- [ ] **Step 1: Cell editors in `renderFinancePage` row map**

Project cell: `<select class="fin-cell-select" data-fin-field="project_id">` options from `state.projects` (not deleted). Work rows: select disabled, single option Работа.

Title cell: task → `<input class="fin-cell-input" data-fin-field="title">`. Work → `<select data-fin-field="work_project_id">` from `work_projects`.

Amount: `<input type="text" inputmode="decimal" data-fin-field="amount">` display with ru grouping ok on blur.

Day: `<input type="date" data-fin-field="day">` empty allowed.

Status: `<select data-fin-field="status"><option value="plan">План</option><option value="confirmed">Подтверждено</option></select>`.

- [ ] **Step 2: Save helpers**

```javascript
function parseLedgerAmount(raw) {
  const t = String(raw || "").replace(/\s/g, "").replace(",", ".").replace("−", "-").replace("–", "-");
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

async function saveLedgerField(row, field, value) {
  if (row.source === "draft") {
    row[field] = value;
    if (field === "project_id") {
      const p = (state.projects || []).find((x) => String(x.id) === String(value));
      row.project_name = p ? p.name : row.project_name;
    }
    if (field === "amount" && Number(row.amount) !== 0) {
      await commitLedgerDraft(row);
    }
    return;
  }
  if (row.source === "task") {
    if (field === "title") {
      await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ title: value }) });
    } else if (field === "project_id") {
      await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ project_id: Number(value) || null }) });
    } else if (field === "amount") {
      const n = Number(value);
      await api(`/api/tasks/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ cost: Math.abs(n), cost_type: n >= 0 ? "income" : "expense" }),
      });
    } else if (field === "day") {
      await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ due_at: value || null }) });
    } else if (field === "status") {
      if (value === "confirmed") await api(`/api/tasks/${row.id}/complete`, { method: "POST" });
      else await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ status: "open" }) });
    }
    await loadFinancePage();
    return;
  }
  if (row.source === "work") {
    const wid = row.work_project_id;
    if (field === "amount") {
      const n = Number(value);
      if (!(n > 0)) {
        alert("Сумма платежа работы должна быть больше 0");
        return;
      }
      await api(`/api/work-projects/${wid}/payments/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ amount: n }),
      });
    } else if (field === "day") {
      await api(`/api/work-projects/${wid}/payments/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ paid_at: value }),
      });
    } else if (field === "status") {
      await api(`/api/work-projects/${wid}/payments/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: value === "plan" ? "planned" : "received" }),
      });
    } else if (field === "work_project_id") {
      const nextId = Number(value);
      if (nextId === wid) return;
      const abs = Math.abs(Number(row.amount) || 0);
      if (!(abs > 0)) return;
      await api(`/api/work-projects/${nextId}/payments`, {
        method: "POST",
        body: JSON.stringify({
          amount: abs,
          paid_at: row.day || undefined,
          status: row.status === "plan" ? "planned" : "received",
        }),
      });
      await api(`/api/work-projects/${wid}/payments/${row.id}`, { method: "DELETE" });
    }
    await loadFinancePage();
  }
}

async function commitLedgerDraft(row) {
  const n = Number(row.amount) || 0;
  if (n === 0) return;
  const personal = (state.projects || []).find((p) => p.name === "Личные дела");
  const title = (row.title || "").trim() || uniqueLedgerDraftTitle();
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title,
      project_id: row.project_id || personal?.id || null,
      cost: Math.abs(n),
      cost_type: n >= 0 ? "income" : "expense",
      due_at: row.day || null,
    }),
  });
  state.financeDrafts = (state.financeDrafts || []).filter((d) => d.id !== row.id);
  await loadFinancePage();
}

function uniqueLedgerDraftTitle() {
  const used = new Set(
    [...(state.financeLedger?.rows || []), ...(state.financeDrafts || [])].map((r) => r.title)
  );
  const base = "Новая строка";
  if (!used.has(base)) return base;
  let i = 2;
  while (used.has(`${base} ${i}`)) i += 1;
  return `${base} ${i}`;
}
```

On API error: `alert(err.message || "Ошибка")` then `loadFinancePage()` to revert.

`data-fin-add-ledger`: push draft `{ source:"draft", id: -Date.now(), project_id: personal.id, project_name:"Личные дела", title: uniqueLedgerDraftTitle(), amount:0, day: todayIso(), status:"plan" }`, re-render, focus title.

Delete selected: if draft, drop from `financeDrafts`. If task, `DELETE /api/tasks/{id}`. If work, `DELETE /api/work-projects/{work_project_id}/payments/{id}`.

- [ ] **Step 3: Events**

Replace `#finance-page` click handler month-shift / category / drawer with:
- filter buttons
- row select (`tr[data-fin-row]`)
- add draft
- close filter on outside click

`change` on `[data-fin-field]` → `saveLedgerField`.

`keydown`: ignore when filter menu open except Esc. Tab between fields in selected row then next row. Enter → next row same field. Arrows move `is-selected` among `tr[data-fin-row]` when focus is not in an input/select (or only when target is the tr). Esc blurs. Delete/Backspace on selected row if focus not in input/select → delete.

Do **not** steal keys outside `#finance-page`.

- [ ] **Step 4: Commit**

```bash
git add static/app.js static/styles.css
git commit -m "feat(finance): inline ledger edit and draft rows"
```

---

### Task 4: Cache bump + browser verify

**Files:**
- Modify: `static/index.html` — `styles.css?v=51`, `app.js?v=78`, `pwa.js?v=14`
- Modify: `static/sw.js` — `CACHE = "notetask-v30"`
- Modify: `static/pwa.js` — `sw.js?v=30`

- [ ] **Step 1: Bump versions as above.** If `sw.js` precaches query strings, bump those too.

- [ ] **Step 2: Restart if needed** (`docker restart notetask`) so Python ledger route loads. Static is bind-mounted — restart still needed for `finance_ledger.py`.

- [ ] **Step 3: Browser** on `http://192.168.0.6/` or `https://todo.baski.pro/`

Verify, **do not enter new live sums** (draft ok if cancelled / amount left 0):

1. Финансы: no Статья/План/Факт/Δ, no month ‹ ›, five columns.
2. Existing cost tasks appear; work payments appear under Проект Работа, Направление = work project title.
3. Open task → Статус План; done → Подтверждено. Planned payment → План.
4. Column filter hides rows; hero income/expense/balance change.
5. Account chips still visible.
6. `+ строка` adds a local row; leave amount 0 so no POST.
7. Tab moves cells. Delete on a **draft** only during verify.

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/sw.js static/pwa.js
git commit -m "chore(web): bump finance ledger cache"
```

---

## Spec coverage

| Spec | Task |
|---|---|
| `GET /api/finance/ledger` rows | 1 |
| Task signed amount + status map | 1 |
| Work payment rows, Проект=Работа | 1 |
| Empty due listed | 1 |
| No zero/deleted | 1 |
| Hero = visible rows, no month nav | 2 |
| Account chips stay | 2 |
| Excel column filters | 2 |
| Five columns, drop budget grid/drawer | 2 |
| Inline cell edit | 3 |
| Draft + POST when Цена ≠ 0 | 3 |
| Delete row | 3 |
| Keyboard Tab/Enter/arrows | 3 |
| Work project change via POST+DELETE | 3 |
| Cache + browser, no new live money | 4 |
| No totals row / no formulas / no Goals / no category drop | (out of plan) |
| Личные дела fin-panel untouched | (do not edit those handlers) |
