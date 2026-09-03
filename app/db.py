from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from .config import DATA_DIR, DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#2f6f4e',
  sort INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source TEXT,
  external_id TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'task',
  priority INTEGER NOT NULL DEFAULT 4,
  due_at TEXT,
  remind_at TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  source TEXT,
  external_id TEXT,
  location TEXT,
  cost REAL,
  cost_type TEXT,
  work_project_id INTEGER REFERENCES work_projects(id),
  repeat_rule TEXT
);

CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL DEFAULT 'Тренировка',
  notes TEXT NOT NULL DEFAULT '',
  started_at TEXT NOT NULL,
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_sets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
  exercise TEXT NOT NULL,
  weight REAL,
  reps INTEGER,
  set_index INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS action_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER,
  payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_action_log_at ON action_log(at);
CREATE INDEX IF NOT EXISTS idx_action_log_entity ON action_log(entity_type, action);

CREATE TABLE IF NOT EXISTS daily_stats (
  day TEXT PRIMARY KEY,
  completions INTEGER NOT NULL DEFAULT 0,
  workouts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS finance_months (
  year_month TEXT PRIMARY KEY,
  income REAL NOT NULL DEFAULT 0,
  expense REAL NOT NULL DEFAULT 0,
  notes TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  client TEXT NOT NULL DEFAULT '',
  budget REAL,
  notes TEXT NOT NULL DEFAULT '',
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_metrics (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_body (
  region TEXT PRIMARY KEY,
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'ok',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_body_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  region TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  target REAL NOT NULL DEFAULT 0,
  unit TEXT NOT NULL DEFAULT '',
  current REAL NOT NULL DEFAULT 0,
  period TEXT NOT NULL DEFAULT 'month',
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_project_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_project_id INTEGER NOT NULL REFERENCES work_projects(id),
  amount REAL NOT NULL,
  paid_at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'received',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  task_id INTEGER,
  sent_at TEXT NOT NULL,
  UNIQUE(kind, dedupe_key)
);

CREATE TABLE IF NOT EXISTS app_notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  kind TEXT NOT NULL,
  task_id INTEGER,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  read_at TEXT
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def ensure_column(db: aiosqlite.Connection, table: str, column: str, ddl: str) -> None:
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


async def migrate(db: aiosqlite.Connection) -> None:
    await ensure_column(db, "tasks", "source", "TEXT")
    await ensure_column(db, "tasks", "external_id", "TEXT")
    await ensure_column(db, "projects", "source", "TEXT")
    await ensure_column(db, "projects", "external_id", "TEXT")
    await ensure_column(db, "tasks", "location", "TEXT")
    await ensure_column(db, "tasks", "cost", "REAL")
    await ensure_column(db, "tasks", "cost_type", "TEXT")
    await ensure_column(db, "tasks", "work_project_id", "INTEGER")
    await ensure_column(db, "tasks", "repeat_rule", "TEXT")
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_source_ext "
        "ON tasks(source, external_id) WHERE external_id IS NOT NULL"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_source_ext "
        "ON projects(source, external_id) WHERE external_id IS NOT NULL"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_list ON tasks(deleted_at, status, kind)"
    )
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at)")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_workout_sets_session ON workout_sets(session_id)"
    )
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS finance_months (
          year_month TEXT PRIMARY KEY,
          income REAL NOT NULL DEFAULT 0,
          expense REAL NOT NULL DEFAULT 0,
          notes TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS work_projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          client TEXT NOT NULL DEFAULT '',
          budget REAL,
          notes TEXT NOT NULL DEFAULT '',
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS health_metrics (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS health_body (
          region TEXT PRIMARY KEY,
          note TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'ok',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS health_body_notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          region TEXT NOT NULL,
          text TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_goals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          target REAL NOT NULL DEFAULT 0,
          unit TEXT NOT NULL DEFAULT '',
          current REAL NOT NULL DEFAULT 0,
          period TEXT NOT NULL DEFAULT 'month',
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS work_project_payments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          work_project_id INTEGER NOT NULL REFERENCES work_projects(id),
          amount REAL NOT NULL,
          paid_at TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'received',
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_work_project_payments_project
          ON work_project_payments(work_project_id);
        CREATE TABLE IF NOT EXISTS notification_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          dedupe_key TEXT NOT NULL,
          task_id INTEGER,
          sent_at TEXT NOT NULL,
          UNIQUE(kind, dedupe_key)
        );
        CREATE TABLE IF NOT EXISTS app_notifications (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          kind TEXT NOT NULL,
          task_id INTEGER,
          title TEXT NOT NULL,
          body TEXT NOT NULL DEFAULT '',
          read_at TEXT
        );
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_health_body_notes_region ON health_body_notes(region, created_at)"
    )
    await db.execute(
        """
        INSERT INTO health_body_notes(region, text, created_at)
        SELECT b.region, b.note, COALESCE(b.updated_at, datetime('now'))
        FROM health_body b
        WHERE TRIM(b.note) != ''
          AND NOT EXISTS (SELECT 1 FROM health_body_notes n WHERE n.region = b.region)
        """
    )
    # forehead → hair (UI region rename)
    await db.execute("UPDATE health_body_notes SET region='hair' WHERE region='forehead'")
    await db.execute(
        """
        INSERT INTO health_body(region, note, status, updated_at)
        SELECT 'hair', note, status, updated_at FROM health_body WHERE region='forehead'
        ON CONFLICT(region) DO NOTHING
        """
    )
    await db.execute("DELETE FROM health_body WHERE region='forehead'")
    await ensure_column(db, "work_project_payments", "status", "TEXT NOT NULL DEFAULT 'received'")
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS finance_categories (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'expense',
          group_name TEXT NOT NULL DEFAULT '',
          sort INTEGER NOT NULL DEFAULT 0,
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS finance_accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          sort INTEGER NOT NULL DEFAULT 0,
          opening_balance REAL NOT NULL DEFAULT 0,
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS finance_transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          category_id INTEGER REFERENCES finance_categories(id),
          account_id INTEGER REFERENCES finance_accounts(id),
          kind TEXT NOT NULL DEFAULT 'expense',
          amount REAL NOT NULL,
          day TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS finance_budget (
          year_month TEXT NOT NULL,
          category_id INTEGER NOT NULL REFERENCES finance_categories(id),
          planned REAL NOT NULL DEFAULT 0,
          PRIMARY KEY (year_month, category_id)
        );
        CREATE INDEX IF NOT EXISTS idx_finance_tx_day ON finance_transactions(day);
        CREATE INDEX IF NOT EXISTS idx_finance_tx_category ON finance_transactions(category_id);
        """
    )


async def connect() -> aiosqlite.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await migrate(db)
    await db.commit()
    return db


async def log_action(
    db: aiosqlite.Connection,
    action: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        "INSERT INTO action_log(at, action, entity_type, entity_id, payload_json) VALUES(?,?,?,?,?)",
        (utcnow(), action, entity_type, entity_id, json.dumps(payload or {}, ensure_ascii=False)),
    )


async def bump_completions(db: aiosqlite.Connection, day: str | None = None) -> None:
    d = day or utcnow()[:10]
    await db.execute(
        """
        INSERT INTO daily_stats(day, completions, workouts) VALUES(?, 1, 0)
        ON CONFLICT(day) DO UPDATE SET completions = completions + 1
        """,
        (d,),
    )


async def bump_workouts(db: aiosqlite.Connection, day: str | None = None) -> None:
    d = day or utcnow()[:10]
    await db.execute(
        """
        INSERT INTO daily_stats(day, completions, workouts) VALUES(?, 0, 1)
        ON CONFLICT(day) DO UPDATE SET workouts = workouts + 1
        """,
        (d,),
    )


def row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


async def ensure_project_catalog(db: aiosqlite.Connection) -> None:
    catalog = [
        ("Inbox", "#2f6f4e", 0),
        ("Личные дела", "#3d7a5a", 1),
        ("Развлечения", "#c45c26", 2),
        ("Работа", "#4073ff", 3),
        ("Здоровье", "#158fad", 4),
        ("Тренировки", "#1f4b7a", 5),
        ("Питание", "#7ecc49", 6),
        ("Покупки", "#c9892e", 7),
        ("Идеи", "#884dff", 8),
    ]
    now = utcnow()
    for name, color, sort in catalog:
        cur = await db.execute(
            "SELECT id FROM projects WHERE deleted_at IS NULL AND name=?",
            (name,),
        )
        row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE projects SET color=?, sort=?, updated_at=? WHERE id=?",
                (color, sort, now, row["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO projects(name, color, sort, created_at, updated_at) VALUES(?,?,?,?,?)",
                (name, color, sort, now, now),
            )
    await db.commit()


async def ensure_defaults(db: aiosqlite.Connection) -> None:
    await ensure_project_catalog(db)


def db_file() -> Path:
    return DB_PATH
