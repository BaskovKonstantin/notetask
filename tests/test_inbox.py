from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

import aiosqlite

from app.db import SCHEMA, ensure_project_catalog
from app.inbox_core import create_item_from_text


async def make_db() -> aiosqlite.Connection:
    tmp = tempfile.mkdtemp(prefix="notetask-test-")
    db = await aiosqlite.connect(Path(tmp) / "test.db")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await ensure_project_catalog(db)
    await db.commit()
    return db


class InboxCoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = await make_db()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_task_phrase_creates_task(self):
        result = await create_item_from_text(
            self.db, "оплатить интернет завтра в 10", source="test"
        )
        self.assertEqual(result["type"], "task")
        self.assertIn("интернет", result["title"])
        cur = await self.db.execute("SELECT COUNT(*) c FROM tasks")
        self.assertEqual((await cur.fetchone())["c"], 1)

    async def test_unparseable_text_becomes_inbox_note(self):
        # The parser treats almost any text as a task; "помощь" is one of the
        # few phrases it rejects — anything rejected must land in Inbox notes.
        result = await create_item_from_text(self.db, "помощь", source="test")
        self.assertEqual(result["type"], "note")
        cur = await self.db.execute(
            "SELECT n.title, p.name AS project FROM notes n "
            "LEFT JOIN projects p ON p.id = n.project_id"
        )
        row = await cur.fetchone()
        self.assertEqual(row["title"], "помощь")
        self.assertEqual(row["project"], "Inbox")
        cur = await self.db.execute("SELECT COUNT(*) c FROM tasks")
        self.assertEqual((await cur.fetchone())["c"], 0)

    async def test_empty_text_is_error(self):
        result = await create_item_from_text(self.db, "   ", source="test")
        self.assertEqual(result["type"], "error")

    async def test_source_logged_in_action_log(self):
        await create_item_from_text(self.db, "купить молоко завтра", source="telegram")
        cur = await self.db.execute(
            "SELECT payload_json FROM action_log WHERE entity_type='task' AND action='created'"
        )
        row = await cur.fetchone()
        self.assertIsNotNone(row)
        self.assertIn('"source": "telegram"', row["payload_json"])


if __name__ == "__main__":
    unittest.main()
